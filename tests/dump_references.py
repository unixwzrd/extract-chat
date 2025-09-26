#!/usr/bin/env python
"""Quick utility to inspect resolved reference metadata for a conversation export.

Usage:
    python tests/dump_references.py tmp/PA-Paper/chatgpt_convo_...json

Outputs one line per unique citation number showing the resolved title, the
source label captured from the “Sources:” block (if present), and the URL host.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable
from urllib.parse import urlparse

from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.reference_utils import extract_reference_groups
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation


def normalize(text: str) -> str:
    return ' '.join(text.lower().split())


def load_reference_groups(json_path: Path):
    conversation = Conversation.model_validate_json(json_path.read_text("utf-8"))
    DocumentContext.initialize(conversation=conversation)
    try:
        blocks = TurnProcessorV2().process_conversation(conversation)
    finally:
        DocumentContext.reset()
    return extract_reference_groups(blocks)


def summarize(groups: Iterable[Dict]) -> Dict[int, Dict[str, str]]:
    summary: Dict[int, Dict[str, str]] = {}
    for group in groups:
        meta = group.get("meta") or {}
        seq = meta.get("seq")
        if not isinstance(seq, int) or seq in summary:
            continue
        title = (meta.get("title") or "").strip()
        label = (meta.get("source_label") or "").strip()
        url = (meta.get("url") or "").strip()
        host = urlparse(url).netloc if url else ""
        summary[seq] = {"title": title, "label": label, "url": url, "host": host}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect resolved reference metadata")
    parser.add_argument("json_path", type=Path, help="Path to ChatGPT JSON export")
    args = parser.parse_args()

    if not args.json_path.exists():
        print(f"error: {args.json_path} does not exist", file=sys.stderr)
        return 1

    groups = load_reference_groups(args.json_path)
    summary = summarize(groups)

    print(f"Found {len(summary)} unique references")
    for seq in sorted(summary):
        info = summary[seq]
        title = info["title"] or "<missing title>"
        label = info["label"] or "<missing label>"
        host = info["host"] or "-"
        flag = ""
        if info["host"] and normalize(title) not in normalize(label) and normalize(label) not in normalize(title):
            flag = " <-- title/label mismatch"
        print(f"{seq:>2}: host={host:20} | title={title} | label={label}{flag}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
