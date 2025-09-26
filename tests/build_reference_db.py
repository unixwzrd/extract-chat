#!/usr/bin/env python
"""Build a lightweight SQLite database of all reference-related artifacts.

Usage
-----
python tests/build_reference_db.py \
    tmp/PA-Paper/chatgpt_convo_....json \
    tmp/PA-Paper/reference_inventory.sqlite \
    --html tmp/PA-Paper/OpenAI-PA-Paper-text.html \
           tmp/PA-Paper/OpenAI-PA-Paper-references.html
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from extract_chat.context.document_context import DocumentContext
from extract_chat.processors.citation_processor import CitationProcessor, _to_dict
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def to_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        raw = {k: v for k, v in value.__dict__.items() if not k.startswith("_")}
        return raw
    return {}


def normalize_text(value: str) -> str:
    import re

    text = value.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def clean_snippet(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text.strip() or None


def open_conversation(json_path: Path):
    convo = Conversation.model_validate_json(json_path.read_text("utf-8"))
    DocumentContext.initialize(conversation=convo)
    try:
        blocks = TurnProcessorV2().process_conversation(convo)
    finally:
        DocumentContext.reset()
    return convo, blocks


def extract_sources_from_markdown(content: str) -> List[Tuple[str, Optional[str]]]:
    if "**Sources:**" not in content:
        return []
    after = content.split("**Sources:**", 1)[1]
    lines = after.splitlines()
    sources: List[Tuple[str, Optional[str]]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            break
        if stripped.startswith("## "):
            break
        sources.append((stripped, None))
    return sources


def extract_sources_from_html(html_path: Path) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html_path.read_text("utf-8"), "html.parser")
    marker = soup.find("strong", string=lambda s: s and s.strip().lower() == "sources:")
    if not marker:
        return []
    parent = marker.find_parent()
    ordered = None
    if parent:
        sibling = parent.find_next_sibling()
        while sibling:
            if sibling.name == "ol":
                ordered = sibling
                break
            sibling = sibling.find_next_sibling()
    if ordered is None:
        ordered = marker.find_next("ol")
    if ordered is None:
        return []

    results: List[Dict[str, Optional[str]]] = []
    seen: set[Tuple[str, Optional[str]]] = set()
    for li in ordered.find_all("li", recursive=False):
        text = " ".join(li.stripped_strings)
        link = li.find("a")
        href = link.get("href") if link and link.has_attr("href") else None
        key = (text, href)
        if key in seen:
            continue
        seen.add(key)
        carrier = li.find(attrs={"data-start": True}) or li.find("p") or li
        data_start = carrier.get("data-start") if carrier else None
        data_end = carrier.get("data-end") if carrier else None
        results.append({"text": text, "href": href, "data_start": data_start, "data_end": data_end})
    return results


def extract_links_from_html(html_path: Path) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html_path.read_text("utf-8"), "html.parser")
    links: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, Optional[str], Optional[str]]] = set()
    for anchor in soup.find_all("a"):
        href = anchor.get("href")
        if not href or not href.startswith("http"):
            continue
        text = " ".join(anchor.stripped_strings)
        attrs = {k: v for k, v in anchor.attrs.items() if k != "href"}
        context = ""
        parent = anchor.parent
        if parent is not None:
            context = parent.get_text(" ", strip=True)
        data_start = None
        data_end = None
        carrier = anchor
        while carrier is not None:
            if carrier.has_attr("data-start"):
                data_start = carrier.get("data-start")
                data_end = carrier.get("data-end")
                break
            carrier = carrier.parent
        key = (href, text, data_start, data_end)
        if key in seen:
            continue
        seen.add(key)
        links.append({
            "text": text,
            "href": href,
            "attrs": attrs,
            "context": context,
            "data_start": data_start,
            "data_end": data_end,
        })
    return links


def extract_text_spans_from_html(html_path: Path) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html_path.read_text("utf-8"), "html.parser")
    results: List[Dict[str, Any]] = []
    seen: set[Tuple[str, int, int, str]] = set()
    for tag in soup.find_all(['strong', 'em']):
        start = tag.get('data-start')
        end = tag.get('data-end')
        if not (start and end):
            continue
        if not start.isdigit() or not end.isdigit():
            continue
        text = tag.get_text(" ", strip=True)
        key = (tag.name, int(start), int(end), text)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                'tag': tag.name,
                'text': text,
                'start_idx': int(start),
                'end_idx': int(end),
            }
        )
    return results


# ---------------------------------------------------------------------------
# SQLite utilities
# ---------------------------------------------------------------------------


def init_db(db_path: Path, overwrite: bool = False) -> sqlite3.Connection:
    if overwrite and db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_items (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            turn_id TEXT,
            parent_turn_id TEXT,
            role TEXT,
            real_author TEXT,
            tool_name TEXT,
            kind TEXT NOT NULL,
            ref_id INTEGER,
            seq INTEGER,
            start_line INTEGER,
            end_line INTEGER,
            start_idx INTEGER,
            end_idx INTEGER,
            title TEXT,
            url TEXT,
            snippet TEXT,
            attribution TEXT,
            source_label TEXT,
            occurrence_label TEXT,
            host TEXT,
            extra JSON
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reference_items_kind ON reference_items(kind)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reference_items_refid ON reference_items(ref_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reference_items_turn ON reference_items(turn_id)")
    return conn


def insert_item(conn: sqlite3.Connection, item: Dict[str, Any]) -> None:
    host = ""
    url = item.get("url") or ""
    if url:
        host = urlparse(url).netloc
    payload = dict(item)
    payload["host"] = host
    payload["extra"] = json.dumps(payload.get("extra", {}), ensure_ascii=False)
    columns = [
        "source",
        "turn_id",
        "parent_turn_id",
        "role",
        "real_author",
        "tool_name",
        "kind",
        "ref_id",
        "seq",
        "start_line",
        "end_line",
        "start_idx",
        "end_idx",
        "title",
        "url",
        "snippet",
        "attribution",
        "source_label",
        "occurrence_label",
        "host",
        "extra",
    ]
    conn.execute(
        f"INSERT INTO reference_items ({', '.join(columns)}) VALUES ({', '.join(['?'] * len(columns))})",
        [payload.get(col) for col in columns],
    )


# ---------------------------------------------------------------------------
# Extraction routines
# ---------------------------------------------------------------------------


def process_conversation(conn: sqlite3.Connection, json_path: Path) -> None:
    convo, blocks = open_conversation(json_path)
    processor = CitationProcessor()
    seq_map: Dict[Tuple[int, int, int], int] = {}
    global_seq = 1

    marker_re = re.compile(r"【(\d+)†L(\d+)-L(\d+)】")

    for turn_id, node in convo.mapping.items():
        node_dict = to_dict(node)
        parent_id = node_dict.get("parent") or None
        message = node_dict.get("message") or {}
        author = message.get("author") or {}
        meta = message.get("metadata") or {}

        role = author.get("role")
        tool_name = author.get("name")
        author_meta = author.get("metadata") or {}
        real_author = author_meta.get("real_author") or meta.get("real_author")

        def base_payload(kind: str) -> Dict[str, Any]:
            return {
                "source": f"json:{json_path.name}",
                "turn_id": turn_id,
                "parent_turn_id": parent_id,
                "role": role,
                "real_author": real_author,
                "tool_name": tool_name,
                "kind": kind,
            }

        # Citations
        citations = meta.get("citations") or []
        for raw in citations:
            entry = _to_dict(raw)
            payload = base_payload("citation")
            payload.update(
                {
                    "start_idx": entry.get("start_ix"),
                    "end_idx": entry.get("end_ix"),
                    "title": entry.get("metadata", {}).get("title"),
                    "url": entry.get("metadata", {}).get("url"),
                    "snippet": clean_snippet(entry.get("metadata", {}).get("text")),
                    "extra": entry,
                }
            )
            insert_item(conn, payload)

        # Content references
        content_refs = meta.get("content_references") or []
        for raw in content_refs:
            entry = _to_dict(raw)
            data = processor._data_from_content_reference(entry)
            marker_text = entry.get("matched_text") or ""
            ref_id = None
            start_line = None
            end_line = None
            match = marker_re.search(marker_text)
            if match:
                try:
                    ref_id = int(match.group(1))
                    start_line = int(match.group(2))
                    end_line = int(match.group(3))
                except ValueError:
                    ref_id = start_line = end_line = None
            if (not data.get("url")) and entry.get("items"):
                item_dicts = [to_dict(it) for it in entry.get("items", [])]
                for item in item_dicts:
                    url = (item.get("url") or "").strip()
                    title = (item.get("title") or "").strip()
                    if url or title:
                        data = {
                            "title": title or data.get("title", ""),
                            "url": url,
                            "text": item.get("snippet") or data.get("text"),
                            "attribution": item.get("attribution") or data.get("attribution"),
                            "pub_date": item.get("pub_date") or data.get("pub_date"),
                        }
                        break
            if (not data.get("url")) and entry.get("fallback_items"):
                fallback_dicts = [to_dict(it) for it in entry.get("fallback_items", [])]
                for item in fallback_dicts:
                    url = (item.get("url") or "").strip()
                    title = (item.get("title") or "").strip()
                    if url or title:
                        data = {
                            "title": title or data.get("title", ""),
                            "url": url,
                            "text": item.get("snippet") or data.get("text"),
                            "attribution": item.get("attribution") or data.get("attribution"),
                            "pub_date": item.get("pub_date") or data.get("pub_date"),
                        }
                        break
            payload = base_payload("content_reference")
            payload.update(
                {
                    "ref_id": ref_id,
                    "start_idx": entry.get("start_idx"),
                    "end_idx": entry.get("end_idx"),
                    "start_line": start_line,
                    "end_line": end_line,
                    "title": data.get("title"),
                    "url": data.get("url"),
                    "snippet": clean_snippet(data.get("text")),
                    "attribution": data.get("attribution"),
                    "extra": entry,
                }
            )
            insert_item(conn, payload)

        # Search results
        search_groups = meta.get("search_result_groups") or []
        for group in search_groups:
            entries = group.get("entries") or group.get("results") or []
            for raw in entries:
                entry = _to_dict(raw)
                ref_id = entry.get("ref_id")
                if isinstance(ref_id, dict):
                    ref_id = None
                payload = base_payload("search_result")
                payload.update(
                    {
                        "ref_id": ref_id,
                        "title": entry.get("title"),
                        "url": entry.get("url"),
                        "snippet": entry.get("snippet") or entry.get("description"),
                        "snippet": clean_snippet(entry.get("snippet") or entry.get("description")),
                        "attribution": entry.get("attribution"),
                        "extra": entry,
                    }
                )
                insert_item(conn, payload)

        # Resolved references for this turn (if any)
        try:
            refs_block, global_seq = processor.get_references_data(
                turn=convo.mapping[turn_id],
                ref_turn_counter=1,
                start_seq=global_seq,
                existing_sequences=seq_map,
            )
        except Exception:
            refs_block = {}
        for ref in refs_block.get("references", []):
            payload = base_payload("resolved_reference")
            payload.update(
                {
                    "ref_id": ref.get("ref_id"),
                    "seq": ref.get("seq"),
                    "start_line": ref.get("start_line"),
                    "end_line": ref.get("end_line"),
                    "title": ref.get("title"),
                    "url": ref.get("url"),
                    "snippet": clean_snippet(ref.get("text")),
                    "attribution": ref.get("attribution"),
                    "source_label": ref.get("source_label"),
                    "occurrence_label": ref.get("occurrence_label"),
                    "extra": ref,
                }
            )
            insert_item(conn, payload)

        # Plain Sources section in message content
        content = message.get("content")
        if isinstance(content, str):
            for idx, (text, _) in enumerate(extract_sources_from_markdown(content), 1):
                payload = base_payload("rendered_source")
                payload.update(
                    {
                        "seq": idx,
                        "title": text,
                        "extra": {"text": text},
                    }
                )
                insert_item(conn, payload)

    DocumentContext.reset()


def ingest_html(conn: sqlite3.Connection, html_path: Path) -> None:
    sources = extract_sources_from_html(html_path)
    for idx, item in enumerate(sources, 1):
        start_idx = end_idx = None
        if item.get("data_start") and str(item["data_start"]).isdigit():
            start_idx = int(item["data_start"])
        if item.get("data_end") and str(item["data_end"]).isdigit():
            end_idx = int(item["data_end"])
        payload = {
            "source": f"html:{html_path.name}",
            "turn_id": None,
            "parent_turn_id": None,
            "role": None,
            "real_author": None,
            "tool_name": None,
            "kind": "html_source",
            "ref_id": None,
            "seq": idx,
            "title": item.get("text"),
            "url": item.get("href"),
            "start_idx": start_idx,
            "end_idx": end_idx,
            "extra": item,
        }
        insert_item(conn, payload)

    links = extract_links_from_html(html_path)
    for idx, item in enumerate(links, 1):
        start_idx = end_idx = None
        if item.get("data_start") and str(item["data_start"]).isdigit():
            start_idx = int(item["data_start"])
        if item.get("data_end") and str(item["data_end"]).isdigit():
            end_idx = int(item["data_end"])
        payload = {
            "source": f"html:{html_path.name}",
            "turn_id": None,
            "parent_turn_id": None,
            "role": None,
            "real_author": None,
            "tool_name": None,
            "kind": "html_link",
            "ref_id": None,
            "seq": idx,
            "title": item.get("text"),
            "url": item.get("href"),
            "start_idx": start_idx,
            "end_idx": end_idx,
            "snippet": clean_snippet(item.get("context")),
            "extra": item,
        }
        insert_item(conn, payload)

    spans = extract_text_spans_from_html(html_path)
    for item in spans:
        payload = {
            "source": f"html:{html_path.name}",
            "turn_id": None,
            "parent_turn_id": None,
            "role": None,
            "real_author": None,
            "tool_name": None,
            "kind": "html_text_span",
            "ref_id": None,
            "seq": None,
            "title": None,
            "url": None,
            "start_idx": item.get("start_idx"),
            "end_idx": item.get("end_idx"),
            "snippet": clean_snippet(item.get("text")),
            "extra": item,
        }
        insert_item(conn, payload)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SQLite reference inventory")
    parser.add_argument("json_path", type=Path, help="Path to ChatGPT conversation JSON")
    parser.add_argument("sqlite_path", type=Path, help="Path to SQLite database to create/update")
    parser.add_argument("--html", type=Path, action="append", help="Additional HTML files to ingest")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing database")
    args = parser.parse_args()

    conn = init_db(args.sqlite_path, overwrite=args.overwrite)
    try:
        process_conversation(conn, args.json_path)
        if args.html:
            for html_path in args.html:
                if html_path.exists():
                    ingest_html(conn, html_path)
        conn.commit()
    finally:
        conn.close()
    print(f"Reference inventory written to {args.sqlite_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
