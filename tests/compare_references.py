#!/usr/bin/env python
"""Compare final resolved references with tool search results and optional HTML snapshot.

This script helps identify citations that were surfaced during the browsing/search
turns but never made it into the final reference list we render.

Examples
--------
$ python tests/compare_references.py \
    tmp/PA-Paper/chatgpt_convo_....json \
    --html tmp/PA-Paper/OpenAI-PA-Paper-text.html
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.reference_utils import extract_reference_groups
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation

# ---------------------------------------------------------------------------
# HTML anchor extractor (standard library only)
# ---------------------------------------------------------------------------


class AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._stack: List[str] = []
        self.items: List[Tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag in {'a', 'li', 'p'}:
            self._stack.append(tag)
        if tag == 'a':
            href = dict(attrs).get('href', '')
            self._stack.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {'a', 'li', 'p'} and self._stack:
            self._stack.pop()
        if tag == 'a' and self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._stack:
            return
        href = ''
        if self._stack and isinstance(self._stack[-1], str) and self._stack[-1].startswith('http'):
            href = self._stack[-1]
        text = data.strip()
        if href and text:
            self.items.append((text, href))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_text(value: str) -> str:
    text = value.lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return text.strip()


def load_conversation(json_path: Path):
    convo = Conversation.model_validate_json(json_path.read_text('utf-8'))
    DocumentContext.initialize(conversation=convo)
    try:
        blocks = TurnProcessorV2().process_conversation(convo)
    finally:
        DocumentContext.reset()
    return convo, blocks


def collect_final_references(blocks) -> Dict[int, Dict[str, str]]:
    groups = extract_reference_groups(blocks)
    summary: Dict[int, Dict[str, str]] = {}
    for group in groups:
        meta = group.get('meta') or {}
        seq = meta.get('seq')
        if not isinstance(seq, int) or seq in summary:
            continue
        # Use reference_title if available, otherwise fall back to title
        reference_title = (meta.get('reference_title') or '').strip()
        title = (meta.get('title') or '').strip()
        display_title = reference_title if reference_title else title
        label = (meta.get('source_label') or '').strip()
        url = (meta.get('url') or '').strip()
        host = urlparse(url).netloc if url else ''
        summary[seq] = {
            'title': display_title,
            'label': label,
            'url': url,
            'host': host,
            'norm_title': normalize_text(display_title),
            'norm_label': normalize_text(label),
        }
    return summary


def collect_search_results(convo) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for node in convo.mapping.values():
        message = getattr(node, 'message', None)
        metadata = getattr(message, 'metadata', None)
        if not metadata:
            continue
        groups = (
            getattr(metadata, 'search_result_groups', None)
            or metadata.get('search_result_groups', [])
            if hasattr(metadata, '__getitem__')
            else []
        )
        for group in groups or []:
            entries = group.get('entries') or group.get('results') or []
            for item in entries:
                entry = item if isinstance(item, dict) else getattr(item, 'dict', lambda: {})()
                url = (entry.get('url') or '').strip()
                title = (entry.get('title') or '').strip()
                snippet = (entry.get('snippet') or entry.get('description') or '').strip()
                if url and title:
                    results.append({
                        'title': title,
                        'url': url,
                        'host': urlparse(url).netloc,
                        'snippet': snippet,
                        'norm_title': normalize_text(title),
                    })
    return results


def collect_html_links(html_path: Path) -> List[Dict[str, str]]:
    collector = AnchorCollector()
    collector.feed(html_path.read_text('utf-8'))
    links: List[Dict[str, str]] = []
    for text, href in collector.items:
        host = urlparse(href).netloc
        if not host:
            continue
        links.append({
            'title': text,
            'url': href,
            'host': host,
            'norm_title': normalize_text(text),
        })
    return links


def best_match(candidate: Dict[str, str], targets: Iterable[Dict[str, str]]) -> Tuple[Optional[int], float]:
    best_seq = None
    best_ratio = 0.0
    for seq, info in targets:
        ratio = difflib.SequenceMatcher(None, candidate['norm_title'], info['norm_title']).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_seq = seq
    return best_seq, best_ratio


def analyze_candidates(name: str, candidates: List[Dict[str, str]], final_refs: Dict[int, Dict[str, str]]) -> None:
    print(f"\n{name}: {len(candidates)} candidates")
    targets = list(final_refs.items())
    for cand in candidates:
        seq, ratio = best_match(cand, targets)
        matched = False
        if seq is not None:
            info = final_refs[seq]
            same_host = bool(cand['host']) and cand['host'] == info['host']
            if same_host and ratio >= 0.6:
                matched = True
            elif ratio >= 0.8:
                matched = True
        if not matched:
            print(f" - {cand['title']} | {cand['url']} | host={cand['host']} | best_seq={seq} ratio={ratio:.2f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare search results with resolved citations")
    parser.add_argument('json_path', type=Path, help='Path to ChatGPT JSON export')
    parser.add_argument('--html', type=Path, action='append', help='Optional HTML snapshot(s) to scan for links')
    args = parser.parse_args()

    convo, blocks = load_conversation(args.json_path)
    final_refs = collect_final_references(blocks)
    search_results = collect_search_results(convo)

    print('Final references:', len(final_refs))
    for seq in sorted(final_refs):
        info = final_refs[seq]
        print(f" {seq:>2}: {info['title']} | host={info['host']} | label={info['label']}")

    analyze_candidates('Search results', search_results, final_refs)

    if args.html:
        for html_path in args.html:
            html_links = collect_html_links(html_path)
            analyze_candidates(f'Links in {html_path.name}', html_links, final_refs)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
