"""Dispatch known source formats to independent parsers before shared rendering."""

from typing import Any

from extract_chat.adapters.base import ParsedSource, SourceAdapter
from extract_chat.adapters.chatgpt import ChatGPTAdapter
from extract_chat.adapters.dots import DotsAdapter
from extract_chat.adapters.hermes import HermesAdapter

SOURCE_ADAPTERS: tuple[SourceAdapter, ...] = (DotsAdapter(), HermesAdapter(), ChatGPTAdapter())


def parse_source(raw: Any, *, adapters: tuple[SourceAdapter, ...] = SOURCE_ADAPTERS) -> ParsedSource:
    """Recognize a source explicitly; never turn an unfamiliar format into an empty transcript."""
    matches = [adapter for adapter in adapters if adapter.matches(raw)]
    if len(matches) != 1:
        raise ValueError("Unsupported or ambiguous conversation JSON; expected a ChatGPT/Work mapping, LogGPT Dots export, or Hermes Desktop session export.")
    return matches[0].parse(raw)


__all__ = ["ParsedSource", "SourceAdapter", "SOURCE_ADAPTERS", "parse_source"]
