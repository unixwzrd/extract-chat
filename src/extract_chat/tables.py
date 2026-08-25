"""Derive portable TSV files from embedded HTML table artifacts."""

from __future__ import annotations

import csv
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from extract_chat.naming import sanitize_title


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _find_html_tables(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        html = value.get("text/html")
        if isinstance(html, str) and "<table" in html.lower():
            found.append(html)
        for child in value.values():
            found.extend(_find_html_tables(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_html_tables(child))
    return found


def write_embedded_tables(
    conversation: Any,
    destination: Path,
    *,
    force: bool = False,
    existing_names: set[str] | None = None,
) -> list[Path]:
    """Write every embedded table as UTF-8 TSV under a derived artifact directory."""

    written: list[Path] = []
    normalized_existing_names = {name.lower() for name in (existing_names or set())}
    destination.mkdir(parents=True, exist_ok=True)
    mapping = getattr(conversation, "mapping", {}) or {}
    for turn in mapping.values():
        message = getattr(turn, "message", None)
        metadata = getattr(message, "metadata", None) if message is not None else None
        if not isinstance(metadata, dict):
            continue
        visualizations = metadata.get("ada_visualizations") or []
        titles = [str(item.get("title") or "table") for item in visualizations if isinstance(item, dict) and item.get("type") == "table"]
        for index, html in enumerate(_find_html_tables(metadata)):
            parser = _TableParser()
            parser.feed(html)
            if not parser.rows:
                continue
            title = titles[min(index, len(titles) - 1)] if titles else f"table-{len(written) + 1}"
            stem = sanitize_title(title)
            if stem.lower() in normalized_existing_names:
                continue
            path = destination / f"{stem}.tsv"
            if path.exists() and not force:
                raise RuntimeError(f"Refusing to overwrite existing table: {path} (use --force)")
            with path.open("w", encoding="utf-8", newline="") as handle:
                csv.writer(handle, dialect="excel-tab", lineterminator="\n").writerows(parser.rows)
            written.append(path)
    return written
