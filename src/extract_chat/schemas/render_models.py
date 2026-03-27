"""Typed intermediate render models for conversation export."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SchemaWarning(BaseModel):
    """Recoverable schema mismatch discovered while loading or inspecting JSON."""

    model_config = ConfigDict(extra="forbid")

    code: str
    path: str
    message: str
    turn_id: str | None = None
    fallback_used: bool = False


class SchemaDiagnostics(BaseModel):
    """Schema mismatch summary emitted during parsing."""

    model_config = ConfigDict(extra="forbid")

    warnings: list[SchemaWarning] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)
    unknown_top_level_keys: list[str] = Field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


class SystemContextEntry(BaseModel):
    """Context block rendered before the transcript."""

    model_config = ConfigDict(extra="forbid")

    title: str
    content: str
    turn_id: str | None = None
    timestamp: float | None = None


class ToolActivityItem(BaseModel):
    """Collapsed activity attached to a visible assistant turn."""

    model_config = ConfigDict(extra="allow")

    category: Literal["tool_call", "tool_output", "hidden_assistant", "reasoning", "internal", "system"]
    title: str
    timestamp: float | None = None
    turn_id: str | None = None
    content_type: str | None = None
    language: str | None = None
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaItem(BaseModel):
    """Media or attachment pointer associated with a transcript turn."""

    model_config = ConfigDict(extra="allow")

    kind: str
    label: str
    url: str | None = None
    turn_id: str | None = None
    message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderTurn(BaseModel):
    """Visible transcript turn."""

    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant", "system"]
    turn_id: str
    timestamp: float | None = None
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    tools_used: list[ToolActivityItem] = Field(default_factory=list)
    media_items: list[MediaItem] = Field(default_factory=list)
    references_table: dict[str, Any] | None = None


class RenderDocument(BaseModel):
    """Typed document handed to formatters."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    conversation_id: str | None = None
    create_time: float | None = None
    update_time: float | None = None
    default_model_slug: str | None = None
    system_context: list[SystemContextEntry] = Field(default_factory=list)
    turns: list[RenderTurn] = Field(default_factory=list)
    schema_diagnostics: SchemaDiagnostics = Field(default_factory=SchemaDiagnostics)

    def __iter__(self):
        return iter(self.get_content_blocks())

    def __len__(self) -> int:
        return len(self.get_content_blocks())

    def get_metadata(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "conversation_id": self.conversation_id,
            "create_time": self.create_time,
            "update_time": self.update_time,
            "default_model_slug": self.default_model_slug,
        }

    def get_content_blocks(self) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for entry in self.system_context:
            blocks.append(
                {
                    "type": "conversation_context",
                    "content": entry.content,
                    "metadata": {
                        "title": entry.title,
                        "turn_id": entry.turn_id,
                        "timestamp": entry.timestamp,
                    },
                }
            )
        for turn in self.turns:
            payload = turn.model_dump()
            payload["type"] = turn.role
            blocks.append(payload)
        return blocks

    def get(self, key: str, default: Any = None) -> Any:
        mapping = {
            "title": self.title,
            "conversation_id": self.conversation_id,
            "create_time": self.create_time,
            "update_time": self.update_time,
            "default_model_slug": self.default_model_slug,
            "content_blocks": self.get_content_blocks(),
            "schema_diagnostics": self.schema_diagnostics,
        }
        return mapping.get(key, default)
