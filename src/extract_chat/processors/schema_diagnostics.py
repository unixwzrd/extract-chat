"""Schema diagnostics helpers for OpenAI conversation JSON."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from extract_chat.schemas.render_models import SchemaDiagnostics, SchemaWarning

_KNOWN_TOP_LEVEL_KEYS = {
    "title",
    "create_time",
    "update_time",
    "mapping",
    "moderation_results",
    "current_node",
    "plugin_ids",
    "conversation_id",
    "conversation_template_id",
    "gizmo_id",
    "gizmo_type",
    "is_archived",
    "is_starred",
    "safe_urls",
    "blocked_urls",
    "default_model_slug",
    "conversation_origin",
    "voice",
    "async_status",
    "disabled_tool_ids",
    "is_do_not_remember",
    "memory_scope",
    "sugar_item_id",
    "root_structure",
    "id",
    "archived",
    "folderId",
    "languageCode",
    "pinned",
    "saveHistory",
    "shouldRefresh",
    "skipped",
    "toneCode",
    "writingStyleCode",
    "temporaryChat",
    "owner",
    "sugar_item_visible",
    "atlas_mode_enabled",
    "context_scopes",
    "is_read_only",
    "pinned_time",
    "context_truncation_continuation",
    "is_study_mode",
    "is_temporary_chat",
}

_KNOWN_CONTENT_TYPES = {
    "text",
    "multimodal_text",
    "thoughts",
    "reasoning_recap",
    "model_editable_context",
    "code",
    "execution_output",
    "tool_result",
    "tool_output",
    "system_error",
    "tether_quote",
    "tether_browsing_display",
    "app_pairing_content",
    "user_editable_context",
}


def analyze_raw_conversation(raw_obj: Any) -> SchemaDiagnostics:
    """Return non-fatal schema warnings for raw conversation JSON."""

    diagnostics = SchemaDiagnostics()
    if not isinstance(raw_obj, Mapping):
        diagnostics.warnings.append(
            SchemaWarning(
                code="invalid_root",
                path="$",
                message="Expected the exported conversation to be a JSON object.",
                fallback_used=False,
            )
        )
        return diagnostics

    unknown_top = sorted(key for key in raw_obj.keys() if key not in _KNOWN_TOP_LEVEL_KEYS)
    diagnostics.unknown_top_level_keys.extend(unknown_top)
    for key in unknown_top:
        diagnostics.warnings.append(
            SchemaWarning(
                code="unknown_top_level_key",
                path=f"$.{key}",
                message=f"Unknown top-level key '{key}' found; export will continue.",
                fallback_used=False,
            )
        )

    mapping = raw_obj.get("mapping")
    if not isinstance(mapping, Mapping):
        diagnostics.warnings.append(
            SchemaWarning(
                code="invalid_mapping",
                path="$.mapping",
                message="Expected 'mapping' to be an object keyed by turn id.",
                fallback_used=False,
            )
        )
        return diagnostics

    content_types: set[str] = set()
    for turn_id, turn_obj in mapping.items():
        turn_path = f"$.mapping.{turn_id}"
        if not isinstance(turn_obj, Mapping):
            diagnostics.warnings.append(
                SchemaWarning(
                    code="invalid_turn",
                    path=turn_path,
                    turn_id=str(turn_id),
                    message="Turn is not a JSON object and may be skipped.",
                    fallback_used=True,
                )
            )
            continue

        if "message" not in turn_obj and ("content" in turn_obj and ("author" in turn_obj or "role" in turn_obj)):
            diagnostics.warnings.append(
                SchemaWarning(
                    code="legacy_flat_turn",
                    path=turn_path,
                    turn_id=str(turn_id),
                    message="Legacy flat turn structure detected; export will normalize it into a nested message.",
                    fallback_used=True,
                )
            )
            message = turn_obj
            message_path = turn_path
        else:
            message = turn_obj.get("message")
            message_path = f"{turn_path}.message"

        if message is None:
            continue
        if not isinstance(message, Mapping):
            diagnostics.warnings.append(
                SchemaWarning(
                    code="invalid_message",
                    path=message_path,
                    turn_id=str(turn_id),
                    message="Turn message is not an object and may be skipped.",
                    fallback_used=True,
                )
            )
            continue

        author = message.get("author")
        if not isinstance(author, Mapping) and isinstance(message.get("role"), str):
            diagnostics.warnings.append(
                SchemaWarning(
                    code="legacy_message_role",
                    path=f"{message_path}.role",
                    turn_id=str(turn_id),
                    message="Legacy message role field detected; export will normalize it into an author object.",
                    fallback_used=True,
                )
            )
        elif not isinstance(author, Mapping):
            diagnostics.warnings.append(
                SchemaWarning(
                    code="invalid_author",
                    path=f"{message_path}.author",
                    turn_id=str(turn_id),
                    message="Message author is missing or not an object.",
                    fallback_used=False,
                )
            )

        content = message.get("content")
        if content is None:
            diagnostics.warnings.append(
                SchemaWarning(
                    code="missing_content",
                    path=f"{message_path}.content",
                    turn_id=str(turn_id),
                    message="Message content is missing.",
                    fallback_used=True,
                )
            )
            continue
        if not isinstance(content, Mapping):
            diagnostics.warnings.append(
                SchemaWarning(
                    code="invalid_content",
                    path=f"{message_path}.content",
                    turn_id=str(turn_id),
                    message="Message content is not an object and may be coerced or skipped.",
                    fallback_used=True,
                )
            )
            continue

        content_type = content.get("content_type")
        if isinstance(content_type, str) and content_type:
            content_types.add(content_type)
            if content_type not in _KNOWN_CONTENT_TYPES:
                diagnostics.warnings.append(
                    SchemaWarning(
                        code="unknown_content_type",
                        path=f"{message_path}.content.content_type",
                        turn_id=str(turn_id),
                        message=f"Unknown content_type '{content_type}' found; rendering will use fallback behavior.",
                        fallback_used=True,
                    )
                )

        metadata = message.get("metadata")
        if metadata is not None and not isinstance(metadata, Mapping):
            diagnostics.warnings.append(
                SchemaWarning(
                    code="invalid_metadata",
                    path=f"{message_path}.metadata",
                    turn_id=str(turn_id),
                    message="Message metadata is not an object; metadata-dependent features may degrade.",
                    fallback_used=True,
                )
            )

    diagnostics.content_types.extend(sorted(content_types))
    return diagnostics
