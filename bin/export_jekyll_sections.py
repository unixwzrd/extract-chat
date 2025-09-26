#!/usr/bin/env python
"""Export a single assistant turn into Jekyll section pages."""

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.jekyll_exporter import JekyllTurnExporter
from extract_chat.schemas.conversation import Conversation

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a single assistant turn into Jekyll section pages.",
    )
    parser.add_argument("input_file", help="Path to the ChatGPT JSON export")
    parser.add_argument(
        "--turn-id",
        required=True,
        help="Assistant turn identifier to export",
    )
    parser.add_argument(
        "--base-slug",
        required=True,
        help="Base slug used for filenames and permalinks (e.g., 2025-09-25-pa-paper)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the Jekyll pages will be written",
    )
    parser.add_argument(
        "--layout",
        default="page",
        help="Layout value to include in the generated front matter (default: page)",
    )
    parser.add_argument(
        "--reference-title",
        default="References",
        help="Title to use for the references page",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in the output directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input_file)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        logger.error("Input file does not exist: %s", input_path)
        sys.exit(1)

    try:
        conversation = Conversation.model_validate_json(input_path.read_text("utf-8"))
    except Exception as exc:
        logger.error("Failed to parse conversation JSON: %s", exc)
        sys.exit(1)

    DocumentContext.initialize(conversation=conversation)

    try:
        exporter = JekyllTurnExporter(base_slug=args.base_slug, layout=args.layout)
        section_pages, references_page = exporter.export_turn(
            conversation=conversation,
            turn_id=args.turn_id,
            reference_page_title=args.reference_title,
        )
    finally:
        DocumentContext.reset()

    output_dir.mkdir(parents=True, exist_ok=True)

    all_pages = section_pages + [references_page]

    for page in all_pages:
        destination = output_dir / page.filename
        if destination.exists() and not args.force:
            logger.error("Refusing to overwrite existing file: %s", destination)
            sys.exit(1)

    for page in all_pages:
        destination = output_dir / page.filename
        destination.write_text(page.content, encoding="utf-8")
        logger.info("Wrote %s", destination)


if __name__ == "__main__":
    main()

