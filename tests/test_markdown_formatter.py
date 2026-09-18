"""Markdown formatter regression tests."""

from datetime import datetime

from extract_chat.formatters.markdown_formatter import MarkdownFormatter


def test_markdown_formatter_handles_internal_dialogue_dict() -> None:
    """Formatting should handle internal dialogue blocks with dict content."""

    block = {
        "type": "internal_dialogue",
        "level": 0,
        "content": {
            "content_type": "thoughts",
            "text": "Plan next action",
            "language": None,
            "thoughts": ["Collect evidence", "Draft summary"],
            "search_queries": [{"q": "latest case law"}],
            "search_result_groups": [
                {
                    "domain": "example.com",
                    "entries": [{"title": "Precedent Overview"}],
                }
            ],
        },
        "metadata": {
            "turn_id": "t-1",
            "timestamp": 1_700_000_000,
            "author_role": "assistant",
            "real_author": "tool:search",
        },
        "additional_info": {
            "url": "https://example.com",
            "domain": "example.com",
        },
    }

    formatter = MarkdownFormatter({"verbose": False})

    output = formatter.format_conversation({"content_blocks": [block]})

    assert "Plan next action" in output
    assert "Search Queries" in output


def test_timestamp_uses_readable_local_time_with_milliseconds() -> None:
    formatter = MarkdownFormatter()

    assert formatter._format_timestamp(datetime(2026, 9, 18, 14, 29, 58, 987654)) == "2026-09-18 14:29:58.987"
    assert formatter._format_timestamp(1_700_000_000.123) == datetime.fromtimestamp(1_700_000_000.123).strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3]
