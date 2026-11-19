#!/usr/bin/env python3
"""Turn processor that builds a typed render document."""

from __future__ import annotations

import logging
from typing import Any

from extract_chat.context.document_context import DocumentContext
from extract_chat.progress import report
from extract_chat.processors.conversation_grouping import group_assistant_updates
from extract_chat.processors.native_activity import attach_native_activity, context_citations, image_generation_info, native_activity_metadata, pair_native_tools, reasoning_text
from extract_chat.processors.reference_processing.citation_processor import CitationProcessor
from extract_chat.schemas.render_models import (
    MediaItem,
    RenderDocument,
    RenderTurn,
    SystemContextEntry,
    ToolActivityItem,
)

logger = logging.getLogger(__name__)

_INTERNAL_CONTENT_TYPES = {
    "model_editable_context",
    "user_editable_context",
    "thoughts",
    "reasoning_recap",
    "code",
    "execution_output",
    "tool_result",
    "tool_call",
    "tool_output",
    "system_error",
    "tether_quote",
    "tether_browsing_display",
    "app_pairing_content",
}


class TurnProcessorV2:
    """Build visible transcript turns with assistant-attached tool activity."""

    def __init__(self) -> None:
        self.reference_turn_counter = 0
        self.global_reference_seq = 1
        self.reference_seq_map: dict[tuple[Any, ...], int] = {}

    def process_conversation(self, conversation: Any) -> RenderDocument:
        """Process the full conversation into a typed render document."""

        dc = DocumentContext.get() or DocumentContext(conversation=conversation)
        ordered_turns = list(dc.iter_chronological())

        document = RenderDocument(
            title=getattr(conversation, "title", None),
            conversation_id=getattr(conversation, "conversation_id", None),
            create_time=getattr(conversation, "create_time", None),
            update_time=getattr(conversation, "update_time", None),
            default_model_slug=getattr(conversation, "default_model_slug", None),
        )

        activities: list[tuple[ToolActivityItem, list[MediaItem]]] = []

        for index, (turn_id, turn_data, _level) in enumerate(ordered_turns):
            report("processing", completed=index, total=len(ordered_turns))
            message = getattr(turn_data, "message", None)
            if not message:
                continue

            classification = self._classify_message(message)
            if classification == "conversation_context":
                document.system_context.extend(self._build_context_entries(message, turn_id))
                continue

            if classification == "skip":
                continue

            if classification == "internal":
                activities.append((self._build_tool_activity(message, turn_id), self._extract_media_items(message, turn_id)))
                continue

            if classification == "assistant":
                turn = self._build_visible_turn(message, turn_id, role="assistant", source_turn=turn_data)
                document.turns.append(turn)
                continue

            if classification == "user":
                document.turns.append(self._build_visible_turn(message, turn_id, role="user"))
                continue

            if classification == "system":
                turn = self._build_visible_turn(message, turn_id, role="system")
                if turn.content.strip():
                    document.turns.append(turn)
                continue

        document.turns = attach_native_activity(document.turns, activities, dc)
        document.turns = group_assistant_updates(document.turns, dc)
        pair_native_tools([item for turn in document.turns for item in turn.tools_used], dc)
        for turn in document.turns:
            turn.tools_used.sort(key=self._tool_sort_key)
            turn.media_items = self._deduplicate_media(turn.media_items)
        return document

    def _classify_message(self, message: Any) -> str:
        role = getattr(getattr(message, "author", None), "role", "unknown")
        metadata = self._metadata(message)
        content = getattr(message, "content", None)
        content_type = getattr(content, "content_type", None)
        text = self._extract_text_content(content).strip()

        if metadata.get("is_user_system_message") or content_type in {"user_editable_context", "model_editable_context"} or metadata.get("user_context_message_data"):
            return "conversation_context"

        if role == "tool":
            return "internal"

        # Final text is user-facing even when its author metadata records a
        # contributing tool (notably real_author=tool:web on search answers).
        if role == "assistant" and getattr(message, "channel", None) == "final" and content_type in {"text", "multimodal_text"} and getattr(message, "recipient", None) in {None, "", "all"} and not metadata.get("is_visually_hidden_from_conversation"):
            return "assistant"

        if self._is_internal(message):
            return "internal"

        if role == "assistant":
            return "assistant"
        if role == "user":
            return "user"
        if role == "system":
            return "system" if text else "skip"
        return "skip"

    def _is_internal(self, message: Any) -> bool:
        metadata = self._metadata(message)
        content = getattr(message, "content", None)
        content_type = getattr(content, "content_type", None)
        role = getattr(getattr(message, "author", None), "role", "unknown")

        if content_type in _INTERNAL_CONTENT_TYPES:
            return True
        if role == "assistant" and (getattr(message, "channel", None) == "analysis" or metadata.get("is_visually_hidden_from_conversation")):
            return True

        author_meta = getattr(getattr(message, "author", None), "metadata", {}) or {}
        real_author = ""
        if isinstance(author_meta, dict):
            real_author = str(author_meta.get("real_author") or "")
        if real_author.startswith("tool:"):
            return True

        if metadata.get("system_hints"):
            return True

        model_slug = str(metadata.get("model_slug") or "")
        if model_slug:
            internal_prefixes = ("research", "browser", "analysis", "search", "tool")
            internal_keywords = ("-browser", "-search", "-tool")
            if any(model_slug.startswith(prefix) for prefix in internal_prefixes):
                return True
            if any(token in model_slug for token in internal_keywords):
                return True

        recipient = str(getattr(message, "recipient", "") or metadata.get("recipient") or "")
        if role == "assistant" and recipient and recipient != "all":
            return True

        if metadata.get("end_turn") is False and role != "user":
            return True

        return False

    def _build_context_entries(self, message: Any, turn_id: str) -> list[SystemContextEntry]:
        content = getattr(message, "content", None)
        metadata = self._metadata(message)
        timestamp = getattr(message, "create_time", None)
        entries: list[SystemContextEntry] = []

        export_context = metadata.get("export_context")
        if isinstance(export_context, dict) and isinstance(export_context.get("text"), str):
            entries.append(SystemContextEntry(title=str(export_context.get("title") or "Export information"), content=export_context["text"], turn_id=turn_id, timestamp=timestamp))

        for title, value in (
            ("User Profile", getattr(content, "user_profile", None)),
            ("User Instructions", getattr(content, "user_instructions", None)),
            ("Model Context", getattr(content, "model_set_context", None)),
        ):
            text = str(value or "").strip()
            if text:
                entries.append(SystemContextEntry(title=title, content=text, turn_id=turn_id, timestamp=timestamp))

        user_context = metadata.get("user_context_message_data") or getattr(message, "user_context_message_data", None) or {}
        if isinstance(user_context, dict):
            for title, key in (("About The User", "about_user_message"), ("About The Model", "about_model_message")):
                text = str(user_context.get(key) or "").strip()
                if text:
                    entries.append(SystemContextEntry(title=title, content=text, turn_id=turn_id, timestamp=timestamp))

        return entries

    def _build_visible_turn(
        self,
        message: Any,
        turn_id: str,
        *,
        role: str,
        source_turn: Any | None = None,
    ) -> RenderTurn:
        content = getattr(message, "content", None)
        metadata = self._metadata(message)
        text = self._extract_text_content(content)
        turn = RenderTurn(
            role=role,
            turn_id=turn_id,
            timestamp=getattr(message, "create_time", None),
            content=text,
            metadata={
                "message_id": getattr(message, "id", None),
                "author": role,
                "author_name": getattr(getattr(message, "author", None), "name", None),
                "status": getattr(message, "status", None),
                "model_slug": metadata.get("model_slug") or getattr(message, "model_slug", None),
                "recipient": getattr(message, "recipient", None),
                "request_id": metadata.get("request_id"),
                "channel": getattr(message, "channel", None),
                "exchange_id": metadata.get("turn_exchange_id") or metadata.get("working_turn_id"),
                "context_citations": context_citations(metadata),
            },
            media_items=self._extract_media_items(message, turn_id),
        )

        if role == "assistant" and source_turn is not None:
            dc = DocumentContext.get()
            has_references = dc.has_references_in_message(message) if dc else self._has_references(message)
            turn.metadata["has_references"] = has_references
            if has_references:
                self.reference_turn_counter += 1
                processor = CitationProcessor()
                refs, next_seq = processor.get_references_data(
                    turn=source_turn,
                    ref_turn_counter=self.reference_turn_counter,
                    start_seq=self.global_reference_seq,
                    existing_sequences=self.reference_seq_map,
                )
                self.global_reference_seq = next_seq
                turn.metadata["reference_turn_number"] = self.reference_turn_counter
                turn.references_table = refs

        return turn

    def _build_tool_activity(self, message: Any, turn_id: str) -> ToolActivityItem:
        metadata = self._metadata(message)
        content = getattr(message, "content", None)
        role = getattr(getattr(message, "author", None), "role", "unknown")
        content_type = getattr(content, "content_type", None)
        text = self._extract_text_content(content)

        category = "internal"
        title = "Internal Activity"
        if content_type == "tool_call":
            category = "tool_call"
            title = f"Tool Call: {getattr(message, 'recipient', None) or 'Unknown tool'}"
        elif role == "tool":
            category = "tool_output"
            title = self._tool_title(message, content_type)
        elif content_type in {"thoughts", "reasoning_recap", "model_editable_context", "user_editable_context"}:
            category = "reasoning"
            title = "Hidden Assistant Activity"
        elif role == "assistant":
            category = "hidden_assistant"
            title = "Hidden Assistant Activity"

        native = metadata.get("source") != "hermes"
        recipient = getattr(message, "recipient", None)
        if native and role == "assistant" and recipient not in {None, "", "all"}:
            category, title = "tool_call", f"Tool call: {recipient}"
        elif native and (content_type in {"thoughts", "reasoning_recap"} or getattr(message, "channel", None) == "analysis"):
            category = "reasoning"
            title = "Reasoning summary" if content_type == "reasoning_recap" else "Reasoning"
            if content_type in {"thoughts", "reasoning_recap"}:
                text = reasoning_text(content.model_dump(exclude_none=True))
        if native and not text:
            text = next((value for key in ("content", "result", "summary") if isinstance(value := getattr(content, key, None), str) and value), "")

        return ToolActivityItem(
            category=category,
            title=title,
            timestamp=getattr(message, "create_time", None),
            turn_id=turn_id,
            content_type=content_type,
            language=getattr(content, "language", None),
            content=text,
            metadata={
                "role": role,
                "source": metadata.get("source"),
                "model_slug": metadata.get("model_slug"),
                "recipient": getattr(message, "recipient", None),
                "request_id": metadata.get("request_id"),
                "status": getattr(message, "status", None),
                "search_queries": metadata.get("search_queries", []),
                "search_result_groups": metadata.get("search_result_groups", []),
                "real_author": self._real_author(message),
                **(native_activity_metadata(message) if native else {}),
            },
        )

    def _tool_title(self, message: Any, content_type: str | None) -> str:
        recipient = str(getattr(getattr(message, "author", None), "name", None) or "").strip()
        real_author = self._real_author(message)
        content_titles = {
            "system_error": "Tool Error",
            "tether_quote": "Browser Quote",
            "tether_browsing_display": "Browser Results",
            "app_pairing_content": "Paired App Context",
            "user_editable_context": "User Editable Context",
        }
        if content_type in content_titles:
            return content_titles[content_type]
        if recipient:
            return f"Tool Output: {recipient}"
        if real_author.startswith("tool:"):
            return f"Tool Output: {real_author[5:]}"
        if content_type:
            return f"Tool Output: {content_type}"
        return "Tool Output"

    def _real_author(self, message: Any) -> str:
        author_meta = getattr(getattr(message, "author", None), "metadata", {}) or {}
        if isinstance(author_meta, dict):
            return str(author_meta.get("real_author") or "")
        return ""

    def _metadata(self, message: Any) -> dict[str, Any]:
        metadata = getattr(message, "metadata", None)
        if isinstance(metadata, dict):
            return metadata
        return {}

    def _tool_sort_key(self, item: ToolActivityItem) -> tuple[float, str]:
        return (item.timestamp or 0.0, item.turn_id or "")

    def _extract_media_items(self, message: Any, turn_id: str) -> list[MediaItem]:
        content = getattr(message, "content", None)
        payloads: list[Any] = []
        if content is not None and hasattr(content, "model_dump"):
            payloads.append(content.model_dump())
        metadata = getattr(message, "metadata", None)
        if isinstance(metadata, dict):
            payloads.append(metadata)
        parts = getattr(content, "parts", None)
        if isinstance(parts, list):
            payloads.append(parts)

        items: list[MediaItem] = []
        seen: set[tuple[str, str]] = set()
        for payload in payloads:
            for candidate in self._iter_media_candidates(payload):
                for kind, value in candidate.items():
                    if kind in {"title", "type", "filename", "name", "mime_type", "image_generation"}:
                        continue
                    label = self._media_label(kind, value)
                    key = (kind, label)
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append(
                        MediaItem(
                            kind=kind,
                            label=label,
                            url=value if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")) else None,
                            turn_id=turn_id,
                            message_id=getattr(message, "id", None),
                            metadata={
                                "value": value,
                                "canonical_id": self._canonical_media_id(candidate.get("file_id")) or self._canonical_media_id(value),
                                "origin": "uploaded" if getattr(getattr(message, "author", None), "role", None) == "user" else "generated",
                                "title": candidate.get("title"),
                                "artifact_type": candidate.get("type"),
                                "image_generation": candidate.get("image_generation"),
                            },
                        )
                    )
        return items

    def _deduplicate_media(self, items: list[MediaItem]) -> list[MediaItem]:
        result: list[MediaItem] = []
        seen: set[str] = set()
        for item in items:
            key = str(item.metadata.get("canonical_id") or item.url or item.label)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _canonical_media_id(self, value: Any) -> str | None:
        text = str(value or "")
        if text.startswith("file-service://"):
            return text[len("file-service://") :]
        if text.startswith("sediment://"):
            return text[len("sediment://") :]
        if text.startswith(("file-", "file_", "CalpicoFile_")):
            return text
        return None

    def _iter_media_candidates(self, value: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if isinstance(value, dict):
            if value.get("type") == "conversation_context_citation":
                return []
            media_keys = (
                "url",
                "content_url",
                "thumbnail_url",
                "image_url",
                "image_urls",
                "download_url",
                "asset_pointer",
                "file_id",
                "audio_asset_pointer",
            )
            matched = {key: value.get(key) for key in media_keys if key in value and value.get(key)}
            if matched:
                generation = image_generation_info(value)
                if generation:
                    matched["image_generation"] = generation
                for context_key in ("title", "type", "filename", "name", "mime_type"):
                    if value.get(context_key):
                        matched[context_key] = value.get(context_key)
                candidates.append(matched)
            for key, child in value.items():
                if key != "conversation_context_citation_metadata":
                    candidates.extend(self._iter_media_candidates(child))
        elif isinstance(value, list):
            for item in value:
                candidates.extend(self._iter_media_candidates(item))
        return candidates

    def _media_label(self, kind: str, value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value[:3])
        return str(value)

    def _extract_text_content(self, content: Any) -> str:
        dc = DocumentContext.get()
        if dc:
            return dc.extract_text_from_content(content)
        if not content:
            return ""
        text = getattr(content, "text", None)
        if text:
            return str(text)
        parts = getattr(content, "parts", None)
        if isinstance(parts, list):
            rendered_parts: list[str] = []
            for part in parts:
                if isinstance(part, str):
                    if part:
                        rendered_parts.append(part)
                    continue
                if isinstance(part, dict):
                    text_value = part.get("text")
                    if text_value:
                        rendered_parts.append(str(text_value))
            return "\n".join(rendered_parts)
        for field in ("thoughts", "model_set_context", "repository", "repo_summary", "result", "summary", "content"):
            value = getattr(content, field, None)
            if value:
                return str(value)
        return ""

    def _has_references(self, message: Any) -> bool:
        metadata = self._metadata(message)
        if metadata.get("citations") or metadata.get("content_references"):
            return True
        text = self._extract_text_content(getattr(message, "content", None))
        return "†L" in text and "【" in text
