#!/usr/bin/env python
"""
CLI entrypoint for extract_chat.

Wraps the v2 extractor using the library modules under src/extract_chat.
"""

import argparse
import logging
import os
import sys

from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters import HTMLFormatter, MarkdownFormatter
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a ChatGPT conversation from JSON using chronological processing.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input_file", help="Path to the input JSON file.")
    parser.add_argument(
        "-o", "--output",
        help="Output filename. If not provided, will use input filename with chosen extension.",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("-c", "--css-file", help="Path to a custom CSS file for HTML output.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output.")
    parser.add_argument("--log-file", help="Optional path to write logs to a file.")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files.")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error("Input file not found: %s", args.input_file)
        sys.exit(1)

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

        # Expose env flag for any legacy debug prints
        if args.verbose:
            os.environ["EXTRACT_CHAT_DEBUG"] = "1"

        # Process conversation
        logger.info("Processing conversation...")
        processor = TurnProcessorV2()
        processed_blocks = processor.process_conversation(conversation)
        adapted = FormatterAdapter(processed_blocks, conversation)

        # Format
        if args.format == "html":
            config = {"css_file": args.css_file, "verbose": args.verbose}
            formatter = HTMLFormatter(config)
        else:
            formatter = MarkdownFormatter({"verbose": args.verbose})
        output_content = formatter.format_conversation(adapted)

        # Write output
        logger.info("Writing output to: %s", output_file)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_content)

        logger.info("Successfully processed conversation: '%s'", conversation.title)
        logger.info("Output written to: %s", output_file)
    except Exception as e:
        logger.error("Error processing file: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
