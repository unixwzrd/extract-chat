"""Compatibility wrapper for citation processor location."""

from typing import Any

from extract_chat.processors.reference_processing.citation_processor import (
    CitationProcessor,
    ReferenceEntry,
)
from extract_chat.processors.reference_processing.reference_utils import _reference_identity_key


def _reference_identity_from_fields(
    url: Any,
    title: Any,
    text: Any,
    ref_id: int,
    seq: int,
    is_fallback: bool = False,
    source_label: Any = "",
    attribution: Any = "",
    line_range: tuple[Any, Any] | None = None,
    reference_title: Any = None,
) -> tuple:
    """Compatibility shim preserving the older 10-argument helper signature."""

    try:
        return ("seq", int(seq))
    except (TypeError, ValueError):
        effective_title = reference_title if reference_title else title
        return _reference_identity_key(
            url,
            effective_title,
            text,
            ref_id,
            seq,
            is_fallback,
            source_label,
            attribution,
            line_range,
        )


__all__ = ["CitationProcessor", "ReferenceEntry", "_reference_identity_from_fields"]
