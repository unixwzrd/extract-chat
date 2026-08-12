"""Canonical, portable names for conversation export packages."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

_SLUG_RE = re.compile(r"[^\w]+", re.UNICODE)


def _timestamp_date(value: Any) -> str | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


def _latest_message_timestamp(conversation: Any) -> float | None:
    latest: float | None = None
    mapping = getattr(conversation, "mapping", {}) or {}
    for turn in mapping.values():
        message = getattr(turn, "message", None)
        value = getattr(message, "create_time", None) if message is not None else None
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            continue
        latest = timestamp if latest is None else max(latest, timestamp)
    return latest


def sanitize_title(value: str | None, *, max_length: int = 140) -> str:
    """Return a filesystem-safe Unicode slug without losing readable words."""

    normalized = unicodedata.normalize("NFKC", str(value or "conversation")).strip()
    slug = _SLUG_RE.sub("-", normalized).strip("-_").lower()
    return (slug or "conversation")[:max_length].rstrip("-_")


def canonical_conversation_stem(conversation: Any) -> str:
    """Build ``start--end--title`` using UTC dates and stable fallbacks."""

    start = _timestamp_date(getattr(conversation, "create_time", None)) or "unknown-date"
    end = (
        _timestamp_date(getattr(conversation, "update_time", None))
        or _timestamp_date(_latest_message_timestamp(conversation))
        or start
    )
    title = sanitize_title(getattr(conversation, "title", None))
    return f"{start}--{end}--{title}"
