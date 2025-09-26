#!/usr/bin/env python
"""Extract the Sources list from an OpenAI chat HTML export.

The script looks for a `<strong>Sources:</strong>` marker and returns each
`<li>` entry along with the first hyperlink (if present).

Example
-------
python tests/extract_openai_sources.py tmp/PA-Paper/OpenAI-PA-Paper-text.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup


def extract_sources(html_path: Path) -> List[Dict[str, Optional[str]]]:
    soup = BeautifulSoup(html_path.read_text("utf-8"), "html.parser")

    marker = soup.find("strong", string=lambda s: s and s.strip().lower() == "sources:")
    if not marker:
        return []
    parent = marker.find_parent()
    ol = None
    if parent:
        sibling = parent.find_next_sibling()
        while sibling:
            if sibling.name == "ol":
                ol = sibling
                break
            sibling = sibling.find_next_sibling()
    if not ol:
        ol = marker.find_next("ol")
    if not ol:
        return []

    results: List[Dict[str, Optional[str]]] = []
    for li in ol.find_all("li", recursive=False):
        text = " ".join(li.stripped_strings)
        link = li.find("a")
        href = link.get("href") if link and link.has_attr("href") else None
        results.append({"text": text, "href": href})
    return results


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract Sources list from OpenAI export HTML")
    parser.add_argument("html_path", type=Path, help="Path to the HTML file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args(argv)

    if not args.html_path.exists():
        print(f"error: {args.html_path} does not exist", file=sys.stderr)
        return 1

    sources = extract_sources(args.html_path)
    if args.json:
        print(json.dumps(sources, ensure_ascii=False, indent=2))
    else:
        print(f"Found {len(sources)} sources in {args.html_path}")
        for idx, item in enumerate(sources, 1):
            href = item["href"] or "-"
            print(f"{idx:02d}: {item['text']} | {href}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
