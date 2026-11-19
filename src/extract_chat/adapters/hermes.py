"""Normalize Hermes Desktop session exports without replaying their tool calls."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, StrictStr

from extract_chat.adapters.base import ParsedSource
from extract_chat.processors.schema_diagnostics import analyze_raw_conversation
from extract_chat.schemas.render_models import SchemaWarning


class HermesFunction(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: StrictStr = Field(min_length=1)
    arguments: StrictStr | dict[str, Any]


class HermesToolCall(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: StrictStr | None = None
    call_id: StrictStr | None = None
    type: Literal["function"] = "function"
    function: HermesFunction


class HermesMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: StrictInt
    message_uid: StrictStr = Field(min_length=1)
    session_id: StrictStr = Field(min_length=1)
    role: Literal["user", "assistant", "system", "tool"]
    timestamp: FiniteFloat = Field(ge=0)
    content: StrictStr
    active: Literal[0, 1] = 1
    compacted: Literal[0, 1] = 0
    compressed_summary: bool = Field(default=False, alias="_compressed_summary", strict=True)
    display_kind: StrictStr | None = None
    reasoning: StrictStr | None = None
    reasoning_content: StrictStr | None = None
    tool_calls: list[HermesToolCall] | None = None
    tool_call_id: StrictStr | None = None
    tool_name: StrictStr | None = None


class HermesExport(BaseModel):
    model_config = ConfigDict(extra="allow")
    exported_at: StrictStr
    session_id: StrictStr = Field(min_length=1)
    title: StrictStr | None = None
    session: dict[str, Any] | None = None
    message_count: StrictInt = Field(ge=0)
    messages: list[HermesMessage]


def _export_timestamp(value: str) -> float:
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("Hermes exported_at must include a time zone.")
    return date.astimezone(timezone.utc).timestamp()


class HermesAdapter:
    name = "hermes"

    def matches(self, raw: Any) -> bool:
        # The desktop exporter has no producer/version marker. Require its
        # envelope, not merely a generic messages array or a suggestive filename.
        return isinstance(raw, dict) and "format" not in raw and "mapping" not in raw and "root_structure" not in raw and {"exported_at", "session_id", "message_count", "messages"}.issubset(raw)

    def parse(self, raw: Any) -> ParsedSource:
        export = HermesExport.model_validate(raw)
        exported_at = _export_timestamp(export.exported_at)
        if export.message_count != len(export.messages):
            raise ValueError("Hermes message_count does not match the exported messages.")
        if not export.messages:
            raise ValueError("The Hermes export contains no messages.")
        if any(message.session_id != export.session_id for message in export.messages):
            raise ValueError("Hermes message session_id does not match the export.")
        for field in ("message_uid", "id"):
            if len({getattr(message, field) for message in export.messages}) != len(export.messages):
                raise ValueError(f"Hermes export has duplicate message {field} values.")
        calls: dict[str, HermesToolCall] = {}
        for message in export.messages:
            if message.tool_calls and message.role != "assistant":
                raise ValueError("Hermes tool calls must belong to an assistant message.")
            for call in message.tool_calls or []:
                identifier = call.call_id or call.id
                if not identifier or identifier in calls:
                    raise ValueError("Hermes tool calls have missing or duplicate identifiers.")
                calls[identifier] = call

        native = {message["message_uid"]: message for message in raw["messages"]}
        summaries = [message for message in export.messages if message.compressed_summary]
        originals = [message for message in export.messages if not message.compressed_summary]
        # active=0 means removed from model context, not removed from history.
        # Keep those originals. Summaries are retained separately, not presented
        # as repeated user prompts. Without originals, show the latest summary.
        summary_only = not originals
        selected = originals or [max(summaries, key=lambda message: message.timestamp)]
        selected = sorted(selected, key=lambda message: message.timestamp)
        mapping: dict[str, Any] = {}
        previous: str | None = None

        def append(identifier: str, role: str, text: str, timestamp: float, *, kind: str = "text", metadata: dict[str, Any] | None = None, source: dict[str, Any] | None = None, recipient: str | None = None) -> None:
            nonlocal previous
            if identifier in mapping or (identifier in native and source is None):
                raise ValueError("Hermes generated activity identifier collides with a source message.")
            mapping[identifier] = {
                "id": identifier, "parent": previous, "children": [],
                "message": {"id": identifier, "author": {"role": role}, "create_time": timestamp,
                            "content": {"content_type": kind, "parts": [text]},
                            "metadata": {"source": "hermes", **(metadata or {})}, "recipient": recipient},
                "native_source": deepcopy(source),
            }
            if previous is not None:
                mapping[previous]["children"].append(identifier)
            previous = identifier

        note = "Hermes Desktop export. This is a derived timeline, not a native conversation branch tree."
        if summaries:
            note += f" {len(summaries)} compaction summary record(s) remain in the original JSON."
            note += " Original messages are shown below, including compacted history; summaries are not duplicated as user dialogue." if originals else " Only summary records are available; the latest summary is shown, not a reconstructed full history."
        append("hermes:export-note", "system", note, selected[0].timestamp, metadata={"is_user_system_message": True, "export_context": {"title": "Hermes export information", "text": note}})
        for message in selected:
            uid = message.message_uid
            metadata = {"hermes_message_uid": uid, "active": message.active, "compacted": message.compacted}
            if summary_only:
                append(uid, "system", "Compaction summary — original messages not present:\n\n" + message.content, message.timestamp, source=native[uid])
                continue
            thoughts = list(dict.fromkeys(text for text in (message.reasoning_content, message.reasoning) if text))
            if thoughts:
                append(f"{uid}:thought", "assistant", "\n\n".join(thoughts), message.timestamp, kind="thoughts")
            kind = "text"
            if message.display_kind == "hidden" or (message.role == "assistant" and message.tool_calls and not message.content.strip()):
                # Call-only assistants are activity, not empty dialogue turns.
                kind = "reasoning_recap"
            call = calls.get(message.tool_call_id or "")
            metadata["request_id"] = message.tool_call_id
            recipient = message.tool_name or (call.function.name if call else None)
            append(uid, message.role, message.content, message.timestamp, kind=kind, metadata=metadata, source=native[uid], recipient=recipient)
            # Requests occur after any accompanying visible reply text, so the
            # common processor keeps requests and subsequent results together.
            for index, call in enumerate(message.tool_calls or []):
                arguments = call.function.arguments
                body = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False, indent=2)
                append(f"{uid}:call:{index}", "assistant", body, message.timestamp, kind="tool_call", metadata={"request_id": call.call_id or call.id}, recipient=call.function.name)

        # The shared processor attaches pending activity to a visible assistant.
        # A tool-only export has no such reply; explicitly label a derived one
        # rather than silently dropping the activity or inventing reply text.
        visible_assistant = any(message.role == "assistant" and message.content.strip() and message.display_kind != "hidden" for message in selected)
        if not summary_only and not visible_assistant and any(message.tool_calls or message.role == "tool" or message.reasoning or message.reasoning_content for message in selected):
            append("hermes:activity-only", "assistant", "[Recorded activity only; no assistant reply text is present in this export.]", selected[-1].timestamp)
        canonical = {
            "title": export.title or "Hermes conversation", "conversation_id": export.session_id,
            "conversation_origin": "hermes", "create_time": min(message.timestamp for message in export.messages),
            "update_time": max(message.timestamp for message in export.messages), "current_node": previous, "mapping": mapping,
        }
        diagnostics = analyze_raw_conversation(canonical)
        for key in sorted(set(raw) - set(HermesExport.model_fields)):
            diagnostics.unknown_top_level_keys.append(key)
            diagnostics.warnings.append(SchemaWarning(code="unknown_hermes_key", path=f"$.{key}", message=f"Unknown Hermes envelope field {key!r}; source data is preserved."))
        canonical["source_metadata"] = {
            "format": "hermes.desktop", "exported_at": exported_at,
            "envelope": deepcopy({key: value for key, value in raw.items() if key != "messages"}),
            "compaction_summaries": [deepcopy(native[message.message_uid]) for message in summaries],
            "derived_mapping": "chronological timeline, not a native branch tree",
        }
        return ParsedSource(self.name, canonical, diagnostics)
