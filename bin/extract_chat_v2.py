#!/usr/bin/env python
"""
Extract Chat V2 - Enhanced approach based on parent-child traversal and comprehensive turn processing.

This script implements the enhanced approach:
1. Read the entire schema into structured models
2. Use parent-child traversal for proper conversation flow
3. Process complete turn structures including all metadata
4. Handle conversation context with proper field extraction
5. Escape triple backticks to prevent markdown formatting issues
"""

import argparse
import logging
import os
import sys

# Add src to path for package imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Require proper installation/layout; no fallbacks
from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters import HTMLFormatter, MarkdownFormatter
from extract_chat.processors.formatter_adapter import FormatterAdapter
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def escape_triple_backticks(text):
    """Escape triple backticks to prevent markdown formatting issues."""
    if not text:
        return text
    return text.replace('```', '\\`\\`\\`')


def main():
    """Main function to parse arguments and run the script."""
    parser = argparse.ArgumentParser(
        description="Extract a ChatGPT conversation from JSON using chronological processing.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Path to the input JSON file."
    )
    parser.add_argument(
        "-o", "--output",
        help="Output filename. If not provided, will use input filename with .md extension."
    )
    parser.add_argument(
        "-f", "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "-c", "--css-file",
        help="Path to a custom CSS file for HTML output."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing files without prompting."
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.input_file):
        logger.error("Input file not found: %s", args.input_file)
        sys.exit(1)

    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        base_name = os.path.splitext(os.path.basename(args.input_file))[0]
        output_file = f"{base_name}.{args.format}"

    # Check if output file exists
    if os.path.exists(output_file) and not args.force:
        response = input(f"File {output_file} already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            logger.info("Operation cancelled.")
            sys.exit(0)

    try:
        # Load JSON directly into Pydantic model
        logger.info("Loading JSON file: %s", args.input_file)
        with open(args.input_file, 'r', encoding='utf-8') as f:
            conversation = Conversation.model_validate_json(f.read())

        # Initialize global document context for downstream processors
        DocumentContext.initialize(conversation=conversation)

        # Process conversation using TurnProcessorV2
        logger.info("Processing conversation...")
        processor = TurnProcessorV2()
        processed_blocks = processor.process_conversation(conversation)

        # Adapt the blocks for the formatter
        processed_conversation = FormatterAdapter(processed_blocks, conversation)

        # Format output
        if args.format == "html":
            config = {"css_file": args.css_file} if args.css_file else None
            formatter = HTMLFormatter(config)
        else:
            formatter = MarkdownFormatter()
        output_content = formatter.format_conversation(processed_conversation)

        # Write output
        logger.info("Writing output to: %s", output_file)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_content)

        logger.info("Successfully processed conversation: '%s'", conversation.title)
        logger.info("Output written to: %s", output_file)

    except Exception as e:
        logger.error("Error processing file: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
