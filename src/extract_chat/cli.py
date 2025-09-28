#!/usr/bin/env python
"""Command line interface for extract_chat."""

import argparse
import logging
import os
import re
import sys
from pathlib import Path

from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters import HTMLFormatter, MarkdownFormatter
from extract_chat.formatters.jekyll_exporter import JekyllTurnExporter
from extract_chat.processors.formatter_adapter import FormatterAdapter
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation


def _maybe_unwrap_structure_analysis(raw_text: str):
    """Support structure-analysis JSON by unwrapping root_structure.fields -> flat dict.

    Returns a JSON text ready for Conversation.model_validate_json if the special
    wrapper is detected; otherwise returns the original text.
    """
    try:
        import json
        obj = json.loads(raw_text)
        if isinstance(obj, dict) and 'root_structure' in obj:
            rs = obj.get('root_structure') or {}
            fields = (rs.get('fields') or {}) if isinstance(rs, dict) else {}
            flat = {}
            for k, v in fields.items():
                if isinstance(v, dict) and 'value' in v:
                    flat[k] = v['value']
            # Only use if we captured a mapping dict
            if 'mapping' in flat and isinstance(flat['mapping'], dict):
                return json.dumps(flat)
    except Exception:
        pass
    return raw_text

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s %(name)s:%(lineno)d: %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str | None) -> str:
    if not value:
        return ""
    slug = value.lower()
    slug = _SLUG_CLEAN_RE.sub("-", slug)
    return slug.strip("-")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a ChatGPT conversation from JSON using chronological processing.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to the input JSON file.")
    parser.add_argument("-o", "--output", help="Output path. For Jekyll format this should be a directory.")
    parser.add_argument(
        "-f", "--format",
        choices=["markdown", "html", "jekyll"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("-c", "--css-file", help="Path to a custom CSS file for HTML output.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output.")
    parser.add_argument("--log-file", help="Optional path to write logs to a file.")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files.")
    parser.add_argument("--jekyll-turn-id", help="Assistant turn ID to export when using --format jekyll.")
    parser.add_argument(
        "--jekyll-base-slug",
        help="Base slug used for generated filenames when using --format jekyll.",
    )
    parser.add_argument(
        "--jekyll-layout",
        default="page",
        help="Layout value to include in generated front matter for Jekyll output (default: page)",
    )
    parser.add_argument(
        "--jekyll-reference-title",
        default="References",
        help="Title to use for the references page when exporting to Jekyll.",
    )

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error("Input file not found: %s", args.input_file)
        sys.exit(1)

    try:
        logger.info("Loading JSON file: %s", args.input_file)
        with open(args.input_file, "r", encoding="utf-8") as f:
            raw_text = f.read()
        raw_text = _maybe_unwrap_structure_analysis(raw_text)
        conversation = Conversation.model_validate_json(raw_text)

        # Configure logging level
        root_logger = logging.getLogger()
        if args.verbose:
            root_logger.setLevel(logging.DEBUG)
        else:
            root_logger.setLevel(logging.INFO)
        if args.log_file:
            fh = logging.FileHandler(args.log_file, encoding='utf-8')
            fh.setLevel(root_logger.level)
            fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s:%(lineno)d: %(message)s'))
            root_logger.addHandler(fh)

        # Initialize shared context
        DocumentContext.initialize(conversation=conversation, verbose=args.verbose)

        try:
            # Expose env flag for any legacy debug prints
            if args.verbose:
                os.environ["EXTRACT_CHAT_DEBUG"] = "1"

            if args.format == "jekyll":
                turn_id = args.jekyll_turn_id
                if not turn_id:
                    logger.error("--jekyll-turn-id is required when using --format jekyll")
                    sys.exit(1)

                base_slug = args.jekyll_base_slug or _slugify(conversation.title)
                if not base_slug:
                    logger.error("Provide --jekyll-base-slug or ensure the conversation has a title to derive one.")
                    sys.exit(1)

                output_dir = Path(args.output) if args.output else Path(base_slug)
                output_dir = output_dir.expanduser().resolve()

                exporter = JekyllTurnExporter(base_slug=base_slug, layout=args.jekyll_layout)
                sections, references_page = exporter.export_turn(
                    conversation=conversation,
                    turn_id=turn_id,
                    reference_page_title=args.jekyll_reference_title,
                )

                all_pages = sections + [references_page]
                if output_dir.exists() and not output_dir.is_dir():
                    logger.error("Output path must be a directory for Jekyll exports: %s", output_dir)
                    sys.exit(1)

                if not args.force:
                    for page in all_pages:
                        destination = output_dir / page.filename
                        if destination.exists():
                            logger.error("Refusing to overwrite existing file: %s (use --force)", destination)
                            sys.exit(1)

                output_dir.mkdir(parents=True, exist_ok=True)
                for page in all_pages:
                    destination = output_dir / page.filename
                    destination.write_text(page.content, encoding="utf-8")
                    logger.info("Wrote %s", destination)

                logger.info(
                    "Jekyll export complete (%d sections + references)",
                    len(sections),
                )
                return

            logger.info("Processing conversation...")
            processor = TurnProcessorV2()
            processed_blocks = processor.process_conversation(conversation)
            adapted = FormatterAdapter(processed_blocks, conversation)

            if args.format == "html":
                config = {"css_file": args.css_file, "verbose": args.verbose}
                formatter = HTMLFormatter(config)
            else:
                formatter = MarkdownFormatter({"verbose": args.verbose})

            output_file = args.output
            if not output_file:
                base_name = os.path.splitext(os.path.basename(args.input_file))[0]
                ext = "md" if args.format == "markdown" else "html"
                output_file = f"{base_name}.{ext}"

            if os.path.exists(output_file) and not args.force:
                resp = input(f"File {output_file} already exists. Overwrite? (y/N): ")
                if resp.strip().lower() not in {"y", "yes"}:
                    logger.info("Operation cancelled.")
                    sys.exit(0)

            output_content = formatter.format_conversation(adapted)

            logger.info("Writing output to: %s", output_file)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_content)

            logger.info("Successfully processed conversation: '%s'", conversation.title)
            logger.info("Output written to: %s", output_file)
        finally:
            DocumentContext.reset()
    except Exception as e:
        logger.error("Error processing file: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
