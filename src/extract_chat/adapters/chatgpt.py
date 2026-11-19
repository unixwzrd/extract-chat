"""ChatGPT and ChatGPT Work share the conversation-mapping input family."""

from collections.abc import Mapping
from typing import Any

from extract_chat.adapters.base import ParsedSource
from extract_chat.processors.schema_diagnostics import analyze_raw_conversation
from extract_chat.processors.schema_normalization import normalize_raw_conversation
from extract_chat.processors.reference_processing.native_markers import normalize_native_references


class ChatGPTAdapter:
    name = "chatgpt"

    def matches(self, raw: Any) -> bool:
        return isinstance(raw, Mapping) and "format" not in raw and ("mapping" in raw or "root_structure" in raw)

    def parse(self, raw: Any) -> ParsedSource:
        if "root_structure" in raw:
            structure = raw.get("root_structure") or {}
            fields = structure.get("fields", {}) if isinstance(structure, Mapping) else {}
            if not isinstance(fields, Mapping):
                fields = {}
            flat = {key: value["value"] for key, value in fields.items() if isinstance(value, Mapping) and "value" in value}
            if isinstance(flat.get("mapping"), Mapping):
                raw = flat
        diagnostics = analyze_raw_conversation(raw)
        return ParsedSource(self.name, normalize_native_references(normalize_raw_conversation(raw, diagnostics)), diagnostics)
