"""
Formatters public API for extract_chat.

This module provides the public interface for all formatters.
"""

from typing import Optional

from pylib.schemas import Conversation

from .base import BaseFormatter, FormattingError
from .html_formatter import HTMLFormatter
from .markdown_formatter import MarkdownFormatter

# Rich metadata functions removed - not used in simplified architecture
# from .rich_metadata import (format_content_references,
#                             format_model_switcher_deny, format_safe_urls,
#                             format_search_results,
#                             format_special_content_types, format_system_hints,
#                             format_tool_metadata)

__all__ = [
    'BaseFormatter',
    'MarkdownFormatter',
    'HTMLFormatter',
    'FormattingError',
    'format_to_markdown',
    'format_to_html',
    # Rich metadata functions removed - not used in simplified architecture
    # 'format_special_content_types',
    # 'format_search_results',
    # 'format_content_references',
    # 'format_safe_urls',
    # 'format_tool_metadata',
    # 'format_system_hints',
    # 'format_model_switcher_deny',
]


def format_to_markdown(document) -> str:
    """
    Convenience function to format a document to Markdown.

    Args:
        document: DocumentIR object

    Returns:
        Formatted Markdown string
    """
    formatter = MarkdownFormatter()
    return formatter.format_document(document)


def format_to_html(conversation: Conversation, config: Optional[dict] = None) -> str:
    """
    Convenience function to format a conversation to HTML.

    Args:
        conversation: Conversation object
        config: Optional configuration dictionary for the HTML formatter

    Returns:
        Formatted HTML string
    """
    formatter = HTMLFormatter(config)
    return formatter.format_conversation(conversation)
