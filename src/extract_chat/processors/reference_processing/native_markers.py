"""Translate exported ChatGPT citation widgets into the existing cite pipeline."""

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any
from urllib.parse import urlsplit


def normalize_native_references(conversation: dict[str, Any]) -> dict[str, Any]:
    for node in (conversation.get("mapping") or {}).values():
        if not isinstance(node, dict) or not isinstance(node.get("message"), dict):
            continue
        message = node["message"]
        content = message.get("content") or {}
        if content.get("content_type") not in {"text", "multimodal_text"}:
            continue
        metadata = message.get("metadata") or {}
        references = metadata.get("content_references") or []
        if not isinstance(references, list):
            continue
        replacements = {}
        normalized = []
        for reference in references:
            if not isinstance(reference, dict):
                normalized.append(reference)
                continue
            matched = reference.get("matched_text")
            if not isinstance(matched, str) or not matched.startswith("\ue200"):
                normalized.append(reference)
                continue
            kind = reference.get("type")
            if kind == "entity":
                label = reference.get("name")
                if not label:
                    try:
                        label = json.loads(matched.split("\ue202", 1)[1].removesuffix("\ue201"))[1]
                    except (ValueError, IndexError, TypeError):
                        label = reference.get("alt") or "Referenced entity"
                replacements[matched] = str(label)
            elif kind == "sources_footnote":
                replacements[matched] = ""  # The formatter writes the source list.
            elif kind in {"grouped_webpages", "webpage", "webpages"}:
                items = reference.get("items") or [reference]
                sources = []
                for item in items:
                    if isinstance(item, dict):
                        sources.append(item)
                        sources.extend(source for source in item.get("supporting_websites", []) or [] if isinstance(source, dict))
                markers = []
                for source in sources:
                    url = source.get("url")
                    if not isinstance(url, str) or urlsplit(url).scheme not in {"http", "https"}:
                        continue
                    identifier = 1_000_000 + int(sha256(url.encode("utf-8")).hexdigest()[:12], 16)
                    marker = f"【{identifier}†L0-L0】"
                    if marker not in markers:
                        markers.append(marker)
                        normalized.append({**deepcopy(source), "matched_text": marker})
                if markers:
                    replacements[matched] = "".join(markers)
                else:
                    normalized.append(reference)
            else:
                normalized.append(reference)
        if replacements:
            metadata["native_content_references"] = deepcopy(references)
            metadata["content_references"] = normalized
            message["metadata"] = metadata
            def replace(text: str) -> str:
                for old, new in replacements.items():
                    text = text.replace(old, new)
                return text
            if isinstance(content.get("text"), str):
                content["text"] = replace(content["text"])
            if isinstance(content.get("parts"), list):
                content["parts"] = [replace(part) if isinstance(part, str) else part for part in content["parts"]]
    return conversation
