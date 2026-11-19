"""Interpret LogGPT's native Dots envelope without treating native user roles as authorship."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from extract_chat.adapters.base import ParsedSource
from extract_chat.processors.schema_diagnostics import analyze_raw_conversation
from extract_chat.schemas.render_models import SchemaWarning


class DotMember(BaseModel):
    model_config = ConfigDict(extra="allow")
    account_user_id: str
    aeon_id: str | None = None
    name: str | None = None


class DotRoom(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    members: list[DotMember]


class DotMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1)
    created_at: str
    updated_at: str | None = None
    account_user_id: str | None = None
    role: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    raw_messages: list[dict[str, Any]] | None = None
    message_metadata: dict[str, Any] = Field(default_factory=dict)
    deleted_at: str | None = None


class DotSource(BaseModel):
    model_config = ConfigDict(extra="allow")
    kind: Literal["dots"]
    scope: Literal["main_timeline"]
    history_complete: Literal[True]
    excluded: list[str] = Field(default_factory=list)


class DotExport(BaseModel):
    model_config = ConfigDict(extra="allow")
    format: Literal["loggpt.dots"]
    format_version: Literal[1]
    title: str
    conversation_id: str
    create_time: float
    update_time: float
    source: DotSource
    dot: dict[str, Any]
    room: DotRoom
    messages: list[DotMessage]


def _timestamp(value: str) -> float:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()


def _role(message: DotMessage, members: dict[str, DotMember]) -> str:
    member = members.get(message.account_user_id or "")
    if member is not None:
        return "assistant" if member.aeon_id else "user"
    if message.raw_messages is not None:
        return "assistant"
    if message.account_user_id is None and message.role == "system":
        return "system"
    raise ValueError(f"Dots message {message.id!r} has an unknown sender; refusing to guess authorship.")


class DotsAdapter:
    name = "dots"

    def matches(self, raw: Any) -> bool:
        return isinstance(raw, dict) and raw.get("format") == "loggpt.dots"

    def parse(self, raw: Any) -> ParsedSource:
        export = DotExport.model_validate(raw)
        if export.conversation_id != export.room.id:
            raise ValueError("Dots export conversation_id does not match its room.")
        members = {member.account_user_id: member for member in export.room.members}
        if len(members) != len(export.room.members):
            raise ValueError("Dots export has duplicate room members.")
        if len({message.id for message in export.messages}) != len(export.messages):
            raise ValueError("Dots export has duplicate message identifiers.")
        native_messages = {message["id"]: message for message in raw["messages"]}
        mapping: dict[str, Any] = {}
        previous: str | None = None
        for message in sorted(export.messages, key=lambda item: _timestamp(item.created_at)):
            role = _role(message, members)
            content = message.content
            native_attachments = content.get("attachments", message.attachments)
            if not isinstance(native_attachments, list):
                raise ValueError(f"Dots message {message.id!r} has invalid attachments.")
            text = content.get("text", "")
            if text is None:
                text = ""  # Attachment-only timeline records have nullable text.
            if not isinstance(text, str):
                raise ValueError(f"Dots message {message.id!r} has invalid text.")
            parts = [text] if text else []
            attachments = []
            embedded = list(message.raw_messages or [])
            for attachment in native_attachments:
                if not isinstance(attachment, dict):
                    raise ValueError(f"Dots message {message.id!r} has a non-object attachment.")
                kind = attachment.get("type")
                if kind == "file":
                    file = attachment.get("file") or {}
                    file_id = attachment.get("file_id") or file.get("file_id") or file.get("id")
                    if not isinstance(file_id, str) or not file_id:
                        raise ValueError("Dots file attachment has no identifier.")
                    attachments.append({
                        "file_id": file_id,
                        "name": file.get("name") or file_id,
                        "mime_type": file.get("mime_type"),
                        "url": f"https://chatgpt.com/backend-api/messaging/rooms/{quote(export.room.id, safe='')}/files/{quote(file_id, safe='')}",
                    })
                elif kind == "thread" and attachment.get("thread_id"):
                    parts.append(f"[Linked Dot task](https://chatgpt.com/dots/thread/{quote(attachment['thread_id'], safe='')}) (task history not included)")
                elif kind == "widget":
                    embedded.extend(attachment.get("messages") or [])
                else:
                    parts.append(f"[{kind or 'Unknown'} attachment preserved in source JSON]")
            for item in embedded:
                item_content = item.get("content") or {}
                item_parts = item_content.get("parts") or []
                if (item.get("author") or {}).get("role") == "assistant":
                    parts.extend(part for part in item_parts if isinstance(part, str))
            if message.deleted_at:
                parts, attachments = ["[Message deleted]"], []
            metadata = deepcopy(message.message_metadata)
            metadata.update({"attachments": attachments, "dots_source_message_id": message.id})
            node = {
                "id": message.id,
                "parent": previous,
                "children": [],
                "message": {
                    "id": message.id,
                    "author": {"role": role, "name": members.get(message.account_user_id or "").name if message.account_user_id in members else None},
                    "create_time": _timestamp(message.created_at),
                    "update_time": _timestamp(message.updated_at or message.created_at),
                    "content": {"content_type": "text", "parts": parts},
                    "metadata": metadata,
                },
                "native_source": deepcopy(native_messages[message.id]),
            }
            if previous is not None:
                mapping[previous]["children"].append(message.id)
            mapping[message.id] = node
            previous = message.id
        canonical = {
            "title": export.title,
            "conversation_id": export.room.id,
            "conversation_origin": "dots",
            "create_time": export.create_time,
            "update_time": export.update_time,
            "current_node": previous,
            "mapping": mapping,
        }
        diagnostics = analyze_raw_conversation(canonical)
        for key in sorted(set(raw) - set(DotExport.model_fields)):
            diagnostics.unknown_top_level_keys.append(key)
            diagnostics.warnings.append(SchemaWarning(code="unknown_dots_key", path=f"$.{key}", message=f"Unknown Dots envelope field {key!r}; source data is preserved."))
        canonical["source_metadata"] = {"format": export.format, "source": deepcopy(raw["source"]), "derived_mapping": "chronological sequence, not a native ChatGPT branch tree"}
        return ParsedSource(self.name, canonical, diagnostics)
