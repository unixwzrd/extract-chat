import json
import re
from pathlib import Path

from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.html_formatter import HTMLFormatter
from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.processors.reference_processing.citation_processor import (
    CitationProcessor,
)
from extract_chat.processors.reference_processing.reference_utils import (
    build_reference_payload,
    extract_reference_groups,
    replace_inline_citation_markers,
)
from extract_chat.schemas.conversation import Conversation

SAMPLE_PATH = Path("tmp/PA-Paper/chatgpt_convo_686ab2a1-6578-8003-b0e6-79b76323e002.json")
TURN_ID = "c3df4f37-ab12-4ab6-a810-6b687a759b83"


def _load_conversation() -> Conversation:
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return Conversation.model_validate(raw)


def _reference_group_count(references_table: dict) -> int:
    groups = extract_reference_groups(
        [
            {
                "type": "assistant",
                "references_table": references_table,
                "metadata": {"reference_turn_number": 1},
            }
        ]
    )
    return len(groups)


def _markdown_reference_numbers(markdown_output: str) -> list[int]:
    if "## References" not in markdown_output:
        return []
    refs_section = markdown_output.split("## References", 1)[1]
    return [int(match) for match in re.findall(r"Ref (\d+)\.", refs_section)]


def _html_reference_numbers(html_output: str) -> list[int]:
    return [int(match) for match in re.findall(r"<strong>Ref (\d+)\.</strong>", html_output)]


def test_extract_reference_groups_deduplicates_source_label_variants() -> None:
    references_table = {
        "references": [
            {
                "unique_id": "turn1_seq1_0_1_10_20",
                "turn_id": 1,
                "ref_id": 14,
                "seq": 1,
                "title": "Example Article",
                "url": "https://example.com/resource",
                "text": "A repeated snippet about policy",
                "attribution": "Example News",
                "start_line": 10,
                "end_line": 20,
            },
            {
                "unique_id": "turn1_seq2_0_2_30_40",
                "turn_id": 1,
                "ref_id": 16,
                "seq": 2,
                "title": "Example Article",
                "url": "https://example.com/resource",
                "text": "A repeated snippet about policy",
                "attribution": "Example News",
                "start_line": 10,
                "end_line": 20,
                "source_label": "Example News",
            },
        ]
    }

    groups = extract_reference_groups(
        [
            {
                "type": "assistant",
                "references_table": references_table,
                "metadata": {"reference_turn_number": 1},
            }
        ]
    )

    assert len(groups) == 1
    group = groups[0]
    assert len(group["occurrences"]) == 2
    occurrence_ref_ids = {entry.get("ref_id") for entry in group["occurrences"]}
    assert occurrence_ref_ids == {14, 16}
    # ensure canonical URL without fragment used
    meta_url = group["meta"].get("url")
    assert isinstance(meta_url, str) and meta_url.startswith("https://example.com/resource")


def test_reference_groups_keep_distinct_line_ranges() -> None:
    references_table = {
        "references": [
            {
                "unique_id": "turn1_seq1_0_1_10_20",
                "turn_id": 1,
                "ref_id": 21,
                "seq": 1,
                "title": "Case Study",
                "url": "https://example.com/article",
                "text": "First quote",
                "start_line": 10,
                "end_line": 20,
            },
            {
                "unique_id": "turn1_seq2_0_2_30_40",
                "turn_id": 1,
                "ref_id": 21,
                "seq": 2,
                "title": "Case Study",
                "url": "https://example.com/article",
                "text": "First quote",
                "start_line": 30,
                "end_line": 40,
            },
        ]
    }

    groups = extract_reference_groups(
        [
            {
                "type": "assistant",
                "references_table": references_table,
                "metadata": {"reference_turn_number": 1},
            }
        ]
    )

    assert len(groups) == 1
    assert {occ["start_line"] for occ in groups[0]["occurrences"]} == {10, 30}


def test_reference_groups_consider_url_fragments() -> None:
    references_table = {
        "references": [
            {
                "unique_id": "turn1_seq1_0_1_10_20",
                "turn_id": 1,
                "ref_id": 42,
                "seq": 1,
                "title": "Article",
                "url": "https://example.com/resource#:~:text=first",
                "text": "Summary of the first section",
                "start_line": 10,
                "end_line": 20,
            },
            {
                "unique_id": "turn1_seq2_0_1_10_20",
                "turn_id": 1,
                "ref_id": 42,
                "seq": 2,
                "title": "Article",
                "url": "https://example.com/resource#:~:text=second",
                "text": "Detailed findings from the second section",
                "start_line": 10,
                "end_line": 20,
            },
        ]
    }

    groups = extract_reference_groups(
        [
            {
                "type": "assistant",
                "references_table": references_table,
                "metadata": {"reference_turn_number": 1},
            }
        ]
    )

    assert len(groups) == 2


def test_short_snippets_are_collapsed() -> None:
    references_table = {
        "references": [
            {
                "unique_id": "turn1_seq1_0_1_10_20",
                "turn_id": 1,
                "ref_id": 55,
                "seq": 1,
                "title": "Article",
                "url": "https://example.com/resource#:~:text=one",
                "text": "Word",
                "start_line": 10,
                "end_line": 20,
            },
            {
                "unique_id": "turn1_seq2_0_1_10_20",
                "turn_id": 1,
                "ref_id": 55,
                "seq": 2,
                "title": "Article",
                "url": "https://example.com/resource#:~:text=two",
                "text": "Word",
                "start_line": 10,
                "end_line": 20,
            },
        ]
    }

    groups = extract_reference_groups(
        [
            {
                "type": "assistant",
                "references_table": references_table,
                "metadata": {"reference_turn_number": 1},
            }
        ]
    )

    assert len(groups) == 1


def test_markdown_and_html_references_are_consistent() -> None:
    conversation = _load_conversation()
    DocumentContext.initialize(conversation=conversation)
    try:
        processor = CitationProcessor()
        references_table, _ = processor.get_references_data(
            turn=conversation.mapping[TURN_ID],
            ref_turn_counter=1,
            start_seq=1,
            existing_sequences={},
        )
        ctx = DocumentContext.get()
        assert ctx is not None
        message = conversation.mapping[TURN_ID].message
        raw_content = ctx.extract_text_from_message(message)
        processed_content = replace_inline_citation_markers(
            raw_content,
            references_table.get("references", []),
        )
    finally:
        DocumentContext.reset()

    conversation_block = {
        "type": "assistant",
        "content": processed_content,
        "references_table": references_table,
        "metadata": {"turn_id": TURN_ID, "reference_turn_number": 1},
    }

    markdown_formatter = MarkdownFormatter()
    markdown_refs_section = markdown_formatter._generate_global_references_section(  # type: ignore[attr-defined]
        [conversation_block]
    )

    html_formatter = HTMLFormatter()
    html_refs_section, html_groups = html_formatter._generate_global_references_section_html(  # type: ignore[attr-defined]
        [conversation_block]
    )

    assert "## References" in markdown_refs_section
    assert "<div" in html_refs_section

    markdown_refs = _markdown_reference_numbers(markdown_refs_section)
    html_refs = _html_reference_numbers(html_refs_section)
    expected_count = _reference_group_count(references_table)

    assert processed_content
    assert "†L" not in processed_content
    assert "Metadata missing" not in processed_content
    assert markdown_refs, "Markdown references section should not be empty"
    assert html_refs, "HTML references section should not be empty"
    assert markdown_refs == sorted(markdown_refs)
    assert html_refs == sorted(html_refs)
    assert markdown_refs == html_refs
    assert len(markdown_refs) == expected_count
    assert len(html_groups) == expected_count

    assert "Metadata missing" not in markdown_refs_section
    assert "Metadata missing" not in html_refs_section


def test_build_reference_payload_assigns_backlink_labels() -> None:
    references_table = {
        "references": [
            {
                "unique_id": "uid1",
                "turn_id": 1,
                "ref_id": 1,
                "seq": 1,
                "title": "Doc One",
                "url": "https://example.com/one",
                "text": "Snippet A",
                "start_line": 10,
                "end_line": 12,
            },
            {
                "unique_id": "uid2",
                "turn_id": 1,
                "ref_id": 1,
                "seq": 1,
                "title": "Doc One",
                "url": "https://example.com/one",
                "text": "Snippet B",
                "start_line": 20,
                "end_line": 22,
            },
            {
                "unique_id": "",
                "turn_id": 1,
                "ref_id": 1,
                "seq": 1,
                "title": "Doc One",
                "url": "https://example.com/one",
                "text": "Snippet orphan",
                "start_line": 30,
                "end_line": 32,
            },
        ]
    }

    payload = build_reference_payload(
        [
            {
                "type": "assistant",
                "references_table": references_table,
                "metadata": {"reference_turn_number": 1},
            }
        ]
    )

    groups = payload["groups"]
    assert len(groups) == 1
    labels = [
        occ.get("backlink_label")
        for occ in groups[0]["occurrences"]
        if occ.get("unique_id")
    ]
    assert labels == ["a", "b"], "Expected alphabetical labels for valid occurrences"
    stats = payload["stats"]
    assert stats["total_occurrences"] == 3
    assert stats["labeled_occurrences"] == 2
    assert stats["orphan_references"] == 0
