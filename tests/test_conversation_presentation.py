"""User-visible replies must not disappear because of provenance metadata."""

from copy import deepcopy
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import json

import pytest

from extract_chat.adapters import parse_source
from extract_chat.context.document_context import DocumentContext
from extract_chat.display_time import display_timestamp, resolve_timezone
from extract_chat.formatters.html_formatter import HTMLFormatter
from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.formatters.turn_index import turn_anchor
from extract_chat.processors.conversation_grouping import group_assistant_updates
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation
from extract_chat.schemas.render_models import MediaItem, RenderDocument, RenderTurn


def render(mapping: dict):
    conversation = Conversation.model_validate({"mapping": mapping})
    try:
        DocumentContext.initialize(conversation=conversation)
        return TurnProcessorV2().process_conversation(conversation)
    finally:
        DocumentContext.reset()


def node(uid: str, role: str, text: str, time: float, **extra: object) -> dict:
    return {"id": uid, "message": {"id": uid, "author": {"role": role}, "create_time": time, "content": {"content_type": "text", "parts": [text]}, **extra}}


def test_final_reply_with_web_provenance_stays_in_dialogue() -> None:
    question = node("question", "user", "Question", 100)
    answer = node("answer", "assistant", "Final answer with sources", 101, channel="final")
    answer["message"]["author"]["metadata"] = {"real_author": "tool:web"}
    followup = node("followup", "user", "Thank you", 102)
    document = render({"question": question, "answer": answer, "followup": followup})
    assert [turn.role for turn in document.turns] == ["user", "assistant", "user"]
    assert document.turns[1].content == "Final answer with sources"


def test_context_fields_do_not_require_the_optional_system_flag() -> None:
    context = node("context", "user", "", 99)
    context["message"]["content"] = {"content_type": "user_editable_context", "user_profile": "Exported profile", "user_instructions": "Exported preferences"}
    document = render({"context": context, "question": node("question", "user", "Question", 100)})
    assert [entry.content for entry in document.system_context] == ["Exported profile", "Exported preferences"]


@pytest.mark.parametrize("sibling", [False, True])
def test_assistant_updates_group_only_with_native_ancestry(sibling: bool) -> None:
    mapping = {"first": node("first", "assistant", "Working", 100), "last": node("last", "assistant", "Done", 102)}
    mapping["last"]["parent"] = "root" if sibling else "tool"
    mapping["tool"] = {**node("tool", "tool", "Result", 101), "parent": "first"}
    conversation = Conversation.model_validate({"mapping": mapping})
    first = RenderTurn(role="assistant", turn_id="first", content="Working", timestamp=100, metadata={"channel": "commentary", "exchange_id": "exchange"}, media_items=[MediaItem(kind="image", label="image.png", url="image.png")])
    last = RenderTurn(role="assistant", turn_id="last", content="Done", timestamp=102, metadata={"channel": "final", "exchange_id": "exchange"})
    try:
        context = DocumentContext.initialize(conversation=conversation)
        result = group_assistant_updates([first, last], context)
    finally:
        DocumentContext.reset()
    if sibling:
        assert len(result) == 2
    else:
        assert len(result) == 1
        assert result[0].content == "Done"
        assert result[0].tools_used[0].content == "Working"
        assert result[0].media_items[0].url == "image.png"
        assert result[0].metadata["component_turn_ids"] == ["first", "last"]
        html = HTMLFormatter({"turn_index": True}).format_document(RenderDocument(turns=result))
        assert f'id="{turn_anchor("first")}"' in html


def test_native_citations_remain_inline_with_references_and_unmodified_source() -> None:
    marker = "\ue200cite\ue202turn0search1\ue202turn0search2\ue201"
    entity = '\ue200entity\ue202["organization","Example Group","description"]\ue201'
    answer = node("answer", "assistant", f"First claim.{marker} Then {entity}.", 100, channel="final", metadata={"content_references": [
        {"type": "grouped_webpages", "matched_text": marker, "items": [{"title": "Primary source", "url": "https://example.com/primary", "supporting_websites": [{"title": "Supporting source", "url": "https://example.org/support"}]}]},
        {"type": "entity", "matched_text": entity, "name": "Example Group"},
    ]})
    raw = {"mapping": {"answer": answer}}
    original = deepcopy(raw)
    normalized = parse_source(raw).conversation
    document = render(normalized["mapping"])
    document.turns[0].media_items.append(MediaItem(kind="url", label="https://example.net/?utm_source=chatgpt.com", url="https://example.net/?utm_source=chatgpt.com"))
    assert raw == original
    assert len(document.turns[0].references_table["references"]) == 2
    for formatter in [HTMLFormatter(), MarkdownFormatter()]:
        text = formatter.format_document(document)
        assert "https://example.com/primary" in text
        assert "https://example.org/support" in text
        assert "Example Group" in text and "\ue200" not in text
        assert text.index("First claim.") < text.index('id="ref-source-') < text.index("Then Example Group")
        assert "References" in text
        assert text.index("<summary>References</summary>") < text.index("<summary>Related links</summary>")
        assert "<summary>Media</summary>" not in text
        assert "utm_source" not in text


def test_timezone_is_date_sensitive_and_preserves_epoch_zero() -> None:
    winter = datetime(2026, 1, 18, 12, tzinfo=timezone.utc)
    summer = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    assert display_timestamp(winter, "America/Chicago") == "2026-01-18 06:00:00.000 CST (UTC-06:00)"
    assert display_timestamp(summer, "America/Chicago") == "2026-07-18 07:00:00.000 CDT (UTC-05:00)"
    assert display_timestamp(summer, "UTC+05:30") == "2026-07-18 17:30:00.000 UTC+05:30 (UTC+05:30)"
    assert MarkdownFormatter({"timezone": "UTC"})._format_timestamp(0) == "1970-01-01 00:00:00.000 UTC (UTC+00:00)"
    for invalid in ["UTC+24:00", "UTC-05:60", "Not/AZone", "../etc/passwd"]:
        with pytest.raises(ValueError):
            resolve_timezone(invalid)


@pytest.mark.parametrize("formatter", [HTMLFormatter, MarkdownFormatter])
def test_turn_index_is_optional_collapsed_and_targets_split_headers(formatter) -> None:
    document = RenderDocument(turns=[RenderTurn(role="user", turn_id="a", content="Question | <script>alert(1)</script>", timestamp=100)])
    assert "Conversation index" not in formatter().format_document(document)
    text = formatter({"turn_index": True, "timezone": "UTC"}).format_document(document)
    assert '<details class="turn-index">' in text
    assert f'href="#{turn_anchor("a")}"' in text
    assert f'id="{turn_anchor("a")}"' in text
    assert "UTC+00:00" in text
    assert "User [Turn:" not in text
    assert "<script>" not in text.split("</details>", 1)[0]


@pytest.mark.parametrize("formatter", [HTMLFormatter, MarkdownFormatter])
def test_index_excerpts_are_bounded_with_ellipsis_and_full_times_remain_in_body(formatter):
    text = "This is a long index example with sufficient words to exceed the compact excerpt length. " * 4
    document = RenderDocument(turns=[RenderTurn(role="user", turn_id="a", content=text, timestamp=100)])
    output = formatter({"turn_index": True, "timezone": "UTC"}).format_document(document)
    index = output.split("<summary>Conversation index</summary>", 1)[1].split("</details>", 1)[0]
    assert "..." in index
    assert "1970-01-01 00:01:40 UTC" in index
    assert "1970-01-01 00:01:40.000 UTC (UTC+00:00)" in output
    assert text.strip() in output
    if formatter is HTMLFormatter:
        class IndexLinks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_link = False
                self.labels = []
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    assert dict(attrs).get("target") is None
                    self.in_link = True
            def handle_endtag(self, tag):
                if tag == "a":
                    self.in_link = False
            def handle_data(self, data):
                if self.in_link:
                    self.labels.append(data)
        parser = IndexLinks()
        parser.feed(index)
        assert 64 < len(parser.labels[0]) <= 80


@pytest.mark.skipif(sys.platform != "darwin", reason="Frozen macOS startup uses the OS timezone database")
def test_frozen_runtime_ignores_developer_timezone_paths(tmp_path: Path) -> None:
    pytest.importorskip("tiktoken")
    hook = Path(__file__).resolve().parents[1] / "macos/runtime_hook.py"
    code = """
import os, runpy, sys, zoneinfo
sys._MEIPASS = sys.argv[2]
os.environ['PYTHONTZPATH'] = '/not-the-runtime/zoneinfo'
zoneinfo.reset_tzpath()
runpy.run_path(sys.argv[1])
assert zoneinfo.TZPATH == ('/usr/share/zoneinfo',)
assert zoneinfo.ZoneInfo('America/Chicago').key == 'America/Chicago'
import tiktoken.load
try:
    tiktoken.load.read_file('https://example.invalid/not-bundled')
except RuntimeError:
    pass
else:
    raise AssertionError('Runtime must never download tokenizer data')
"""
    result = subprocess.run([sys.executable, "-c", code, str(hook), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_parts_markdown_lists_render_without_an_extra_blank_line() -> None:
    text = 'Intro:\n- First **point**\n- Second point\n  - Nested point\n\nSteps:\n1. Start\n2. Finish\n\n```text\n- literal code, not a list\n```'
    raw = json.loads(json.dumps({"mapping": {"a": node("a", "assistant", text, 100)}}))
    document = render(parse_source(raw).conversation["mapping"])
    html = HTMLFormatter().format_document(document)
    assert '<li>First <strong>point</strong></li>' in html
    assert '<li>Nested point</li>' in html
    assert '<ol>' in html and '<li>Finish</li>' in html
    assert '<code class="language-text">- literal code, not a list' in html
    assert text in MarkdownFormatter().format_document(document)
    assert raw["mapping"]["a"]["message"]["content"]["parts"][0] == text


def test_commonmark_keeps_tables_and_generated_citations_but_not_executable_html() -> None:
    formatter = HTMLFormatter()
    table = '| A | B |\n| --- | --- |\n| 1 | 2 |'
    assert '<table>' in formatter._convert_markdown_to_html(table)
    citation = '<sup id="ref-source-1"><a href="#ref-target-1">[1]</a></sup>'
    assert citation in formatter._convert_markdown_to_html('Claim. ' + citation)
    assert citation in formatter._convert_markdown_to_html(citation)
    for payload in ['<script>alert(1)</script>', 'Text <img src=x onerror="alert(1)">', '<iframe src="https://example.org"></iframe>']:
        output = formatter._convert_markdown_to_html(payload)
        assert '<script' not in output and '<img' not in output and '<iframe' not in output
