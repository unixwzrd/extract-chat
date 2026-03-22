"""Markdown formatter for typed conversation render documents."""

from __future__ import annotations

from typing import Any

from extract_chat.formatters.base import BaseFormatter, FormattingError
from extract_chat.processors.reference_processing.reference_utils import (
    build_reference_payload,
    format_apa_reference_entry,
    replace_inline_citation_markers,
    strip_sources_and_references,
)
from extract_chat.schemas.render_models import MediaItem, RenderDocument, RenderTurn, ToolActivityItem


class MarkdownFormatter(BaseFormatter):
    """Render conversation logs to Markdown."""

    def get_file_extension(self) -> str:
        return "md"

    def get_mime_type(self) -> str:
        return "text/markdown"

    def format_document(self, document: Any) -> str:
        return self.format_conversation(document)

    def format_conversation(self, conversation: Any) -> str:
        try:
            document = self._coerce_document(conversation)
            lines: list[str] = []

            metadata = document.get_metadata()
            title = metadata.get("title")
            if title:
                lines.append(f"# {title}")
                lines.append("")

            if metadata.get("conversation_id"):
                lines.append(f"**Conversation ID:** {metadata['conversation_id']}")
                lines.append("")

            if metadata.get("create_time"):
                lines.append(f"**Created:** {self._format_timestamp(metadata['create_time'])}")
            if metadata.get("update_time"):
                lines.append(f"**Last Update:** {self._format_timestamp(metadata['update_time'])}")
            if metadata.get("create_time") or metadata.get("update_time"):
                lines.append("")
            if metadata.get("default_model_slug"):
                lines.append(f"**Default Model:** {metadata['default_model_slug']}")
                lines.append("")

            lines.append("---")
            lines.append("")

            if document.system_context:
                lines.append("## System Context")
                lines.append("")
                for entry in document.system_context:
                    lines.append(f"### {entry.title}")
                    lines.append("")
                    lines.append(entry.content)
                    lines.append("")
                lines.append("---")
                lines.append("")

            lines.append("## Conversation")
            lines.append("")

            for turn in document.turns:
                lines.extend(self._render_turn(turn))

            return self._normalize_text("\n".join(lines).rstrip() + "\n")
        except Exception as exc:
            raise FormattingError(f"Failed to format conversation: {exc}", self) from exc

    def _coerce_document(self, conversation: Any) -> RenderDocument:
        if isinstance(conversation, RenderDocument):
            return conversation
        if isinstance(conversation, dict) and "content_blocks" in conversation:
            return self._legacy_document_from_blocks(conversation.get("content_blocks") or [])
        if hasattr(conversation, "model_dump"):
            return RenderDocument.model_validate(conversation.model_dump())
        return RenderDocument.model_validate(conversation)

    def _legacy_document_from_blocks(self, blocks: list[dict[str, Any]]) -> RenderDocument:
        document = RenderDocument()
        for block in blocks:
            block_type = block.get("type")
            metadata = block.get("metadata", {}) or {}
            if block_type == "conversation_context":
                document.system_context.append(
                    {
                        "title": metadata.get("title", "Context"),
                        "content": str(block.get("content") or ""),
                        "turn_id": metadata.get("turn_id"),
                        "timestamp": metadata.get("timestamp"),
                    }
                )
            elif block_type == "internal_dialogue":
                content = block.get("content") or {}
                document.turns.append(
                    RenderTurn(
                        role="assistant",
                        turn_id=str(metadata.get("turn_id") or "legacy"),
                        timestamp=metadata.get("timestamp"),
                        tools_used=[
                            ToolActivityItem(
                                category="internal",
                                title="Tools Used",
                                timestamp=metadata.get("timestamp"),
                                turn_id=metadata.get("turn_id"),
                                content_type=content.get("content_type"),
                                content=content.get("text", ""),
                                metadata={
                                    **metadata,
                                    "search_queries": content.get("search_queries", []),
                                    "search_result_groups": content.get("search_result_groups", []),
                                },
                            )
                        ],
                    )
                )
            elif block_type in {"assistant", "user", "system"}:
                document.turns.append(
                    RenderTurn(
                        role=block_type,
                        turn_id=str(metadata.get("turn_id") or "legacy"),
                        timestamp=metadata.get("timestamp"),
                        content=str(block.get("content") or ""),
                        metadata=metadata,
                        references_table=block.get("references_table"),
                    )
                )
        return document

    def _render_turn(self, turn: RenderTurn) -> list[str]:
        lines = [f"### {turn.role.title()} [Turn: {turn.turn_id}]"]
        if turn.timestamp:
            lines.append(f"*{self._format_timestamp(turn.timestamp)}*")
        lines.append("")

        if turn.role == "assistant" and turn.tools_used:
            lines.append(self._render_tools_used(turn.tools_used))
            lines.append("")

        content = turn.content or ""
        if turn.role == "assistant" and turn.references_table:
            refs = turn.references_table.get("references", [])
            if refs:
                content = replace_inline_citation_markers(content, refs)
        content, _sources = strip_sources_and_references(content)
        if content.strip():
            lines.append(content.strip())
            lines.append("")

        if turn.media_items:
            lines.append(self._render_media(turn.media_items))
            lines.append("")

        if turn.role == "assistant" and turn.references_table:
            rendered_references = self._render_reference_details(turn)
            if rendered_references:
                lines.append(rendered_references)
                lines.append("")

        return lines

    def _render_tools_used(self, tools: list[ToolActivityItem]) -> str:
        lines = ["<details>", "<summary>Tools Used</summary>", ""]
        for item in tools:
            lines.append(f"**{item.title}**")
            meta_bits: list[str] = []
            if item.timestamp:
                meta_bits.append(self._format_timestamp(item.timestamp))
            if item.content_type:
                meta_bits.append(item.content_type)
            if item.turn_id:
                meta_bits.append(f"Turn: {item.turn_id}")
            model_slug = item.metadata.get("model_slug")
            if model_slug:
                meta_bits.append(f"Model: {model_slug}")
            if meta_bits:
                lines.append(f"*{' | '.join(meta_bits)}*")
            if item.content:
                if item.language:
                    lines.append(f"```{item.language}")
                    lines.append(item.content)
                    lines.append("```")
                else:
                    lines.append(item.content)
            search_queries = item.metadata.get("search_queries") or []
            if search_queries:
                lines.append("")
                lines.append("Search Queries:")
                for query in search_queries:
                    query_text = query.get("q") if isinstance(query, dict) else str(query)
                    if query_text:
                        lines.append(f"- {query_text}")
            lines.append("")
        lines.append("</details>")
        return "\n".join(lines).strip()

    def _render_media(self, media_items: list[MediaItem]) -> str:
        lines = ["<details>", "<summary>Media</summary>", ""]
        for item in media_items:
            lines.append(f"**{item.kind}**")
            local_path = item.metadata.get("local_path")
            original_url = item.metadata.get("original_url")
            canonical_id = item.metadata.get("canonical_id")
            if item.url and local_path:
                lines.append(f"- Local: [{item.label}]({item.url})")
                if canonical_id:
                    lines.append(f"- File ID: `{canonical_id}`")
                if original_url:
                    lines.append(f"- Remote: `{original_url}`")
            elif item.url:
                lines.append(f"- Link: [{item.label}]({item.url})")
            else:
                lines.append(f"- Value: `{item.label}`")
            lines.append("")
        lines.append("</details>")
        return "\n".join(lines).strip()

    def _render_reference_details(self, turn: RenderTurn) -> str:
        payload = build_reference_payload(
            [
                {
                    "type": "assistant",
                    "references_table": turn.references_table or {},
                    "metadata": {"reference_turn_number": turn.metadata.get("reference_turn_number")},
                }
            ]
        )
        groups = payload.get("groups", [])
        if not groups:
            return ""

        lines = ["<details>", "<summary>References</summary>", ""]
        for index, group in enumerate(groups, start=1):
            meta = group.get("meta") or {}
            occurrences = group.get("occurrences") or []
            anchors = " ".join(
                f'<a id="ref-target-{occ.get("unique_id")}"></a>'
                for occ in occurrences
                if occ.get("unique_id")
            )
            seq = meta.get("seq") or index
            citation = format_apa_reference_entry(meta, html=False)
            snippets: list[str] = []
            text = (meta.get("text") or "").strip().replace("\n", " ")
            if text and not meta.get("is_fallback"):
                snippets.append(f'"{text}"')
            backlinks = [
                f"[{occ.get('backlink_label')}^](#ref-source-{occ.get('unique_id')})"
                for occ in occurrences
                if occ.get("unique_id") and occ.get("backlink_label")
            ]
            line = f"- Ref {seq}. {citation}"
            if snippets:
                line = f"{line} {' '.join(snippets)}"
            if backlinks:
                line = f"{line} {', '.join(backlinks)}"
            if anchors:
                line = f"{anchors} {line}"
            lines.append(line.strip())
            lines.append("")
        lines.append("</details>")
        return "\n".join(lines).strip()

    def _generate_global_references_section(self, conversation_blocks: list[dict[str, Any]]) -> str:
        payload = build_reference_payload(conversation_blocks)
        groups = payload.get("groups", [])
        if not groups:
            return ""
        lines = ["## References", ""]
        for index, group in enumerate(groups, start=1):
            meta = group.get("meta") or {}
            occurrences = group.get("occurrences") or []
            anchors = " ".join(
                f'<a id="ref-target-{occ.get("unique_id")}"></a>'
                for occ in occurrences
                if occ.get("unique_id")
            )
            seq = meta.get("seq") or index
            citation = format_apa_reference_entry(meta, html=False)
            backlinks = [
                f"[{occ.get('backlink_label')}^](#ref-source-{occ.get('unique_id')})"
                for occ in occurrences
                if occ.get("unique_id") and occ.get("backlink_label")
            ]
            line = f"- Ref {seq}. {citation}"
            if backlinks:
                line = f"{line} {', '.join(backlinks)}"
            if anchors:
                line = f"{anchors} {line}"
            lines.append(line)
            lines.append("")
        return "\n".join(lines).strip()
