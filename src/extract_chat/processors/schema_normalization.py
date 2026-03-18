"""Normalization helpers for legacy OpenAI conversation export variants."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from extract_chat.schemas.render_models import SchemaDiagnostics, SchemaWarning

_MESSAGE_FIELDS = {
    "id",
    "author",
    "role",
    "content",
    "create_time",
    "update_time",
    "status",
    "end_turn",
    "weight",
    "metadata",
    "recipient",
    "channel",
}


def normalize_raw_conversation(raw_obj: Any, diagnostics: SchemaDiagnostics | None = None) -> Any:
    """Coerce legacy export shapes into the canonical conversation schema."""

    if not isinstance(raw_obj, Mapping):
        return raw_obj

    normalized = deepcopy(raw_obj)
    mapping = normalized.get("mapping")
    if not isinstance(mapping, dict):
        return normalized

    for turn_id, turn_obj in list(mapping.items()):
        if not isinstance(turn_obj, Mapping):
            continue
        mapping[turn_id] = _normalize_turn(turn_id=str(turn_id), turn_obj=dict(turn_obj), diagnostics=diagnostics)

    return normalized


def _normalize_turn(turn_id: str, turn_obj: dict[str, Any], diagnostics: SchemaDiagnostics | None) -> dict[str, Any]:
    if "message" not in turn_obj and _looks_like_flat_turn(turn_obj):
        message = {key: turn_obj.get(key) for key in _MESSAGE_FIELDS if key in turn_obj}
        turn_obj = {
            "id": turn_obj.get("id", turn_id),
            "parent": turn_obj.get("parent"),
            "children": turn_obj.get("children", []),
            "create_time": turn_obj.get("create_time"),
            "update_time": turn_obj.get("update_time"),
            "archived": turn_obj.get("archived"),
            "pinned": turn_obj.get("pinned"),
            "message": _normalize_message(message, turn_id=turn_id, diagnostics=diagnostics, path=f"$.mapping.{turn_id}"),
        }
        _add_warning(
            diagnostics,
            SchemaWarning(
                code="legacy_flat_turn",
                path=f"$.mapping.{turn_id}",
                turn_id=turn_id,
                message="Legacy flat turn structure detected and normalized into a nested message.",
                fallback_used=True,
            ),
        )
        return turn_obj

    message = turn_obj.get("message")
    if isinstance(message, Mapping):
        turn_obj["message"] = _normalize_message(
            dict(message),
            turn_id=turn_id,
            diagnostics=diagnostics,
            path=f"$.mapping.{turn_id}.message",
        )
    return turn_obj


def _normalize_message(
    message_obj: dict[str, Any],
    *,
    turn_id: str,
    diagnostics: SchemaDiagnostics | None,
    path: str,
) -> dict[str, Any]:
    role = message_obj.get("role")
    author = message_obj.get("author")
    if not isinstance(author, Mapping) and isinstance(role, str):
        message_obj["author"] = {"role": role, "metadata": {}}
        _add_warning(
            diagnostics,
            SchemaWarning(
                code="legacy_message_role",
                path=f"{path}.role",
                turn_id=turn_id,
                message="Legacy message role field detected and normalized into an author object.",
                fallback_used=True,
            ),
        )
    return message_obj


def _looks_like_flat_turn(turn_obj: Mapping[str, Any]) -> bool:
    return "content" in turn_obj and ("author" in turn_obj or "role" in turn_obj)


def _add_warning(diagnostics: SchemaDiagnostics | None, warning: SchemaWarning) -> None:
    if diagnostics is None:
        return
    existing = {(item.code, item.path, item.turn_id) for item in diagnostics.warnings}
    key = (warning.code, warning.path, warning.turn_id)
    if key not in existing:
        diagnostics.warnings.append(warning)
