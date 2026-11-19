"""Compare rendered Markdown with standalone HTML, not their source markup.

Set EXTRACT_CHAT_REVIEW_DIR to also audit private, already-extracted samples.
Private conversations are never required by the ordinary regression suite.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from html.parser import HTMLParser
import os
from pathlib import Path

from markdown_it import MarkdownIt
import pytest

from extract_chat.adapters import parse_source
from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.html_formatter import HTMLFormatter
from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation
from extract_chat.schemas.render_models import (
    MediaItem, RenderDocument, RenderTurn, SystemContextEntry, ToolActivityItem,
)


def normalized(text: str) -> str:
    return " ".join(text.split())


@dataclass
class Element:
    tag: str
    attrs: dict
    children: list[Element | str] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.walk()

    def text(self) -> str:
        return "".join(child.text() if isinstance(child, Element) else child for child in self.children)


class Fragment(HTMLParser):
    """Small inert tree for comparing the visible conversation, not activity."""
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.root = Element("root", {})
        self.stack = [self.root]
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Element(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def semantic_node(node: Element | str, *, verbatim: bool = False) -> tuple:
    if isinstance(node, str):
        text = node if verbatim else normalized(node)
        return ("text", text) if text else ()
    attributes = tuple((key, node.attrs[key]) for key in ("href", "src", "alt", "start") if key in node.attrs)
    children = tuple(value for child in node.children if (value := semantic_node(child, verbatim=verbatim or node.tag == "pre")))
    return node.tag, attributes, children


def visible_turns(text: str) -> list[tuple]:
    root = Fragment(text).root
    articles = [node for node in root.walk() if node.tag == "article" and "block" in node.attrs.get("class", "").split()]
    if articles:
        turns = []
        for article in articles:
            role = next(node.text() for node in article.walk() if node.tag == "h3")
            if role == "Exported activity":
                continue
            body = next((node.children for node in article.walk() if node.tag == "div" and "content" in node.attrs.get("class", "").split()), [])
            turns.append((role, tuple(value for node in body if (value := semantic_node(node)))))
        return turns
    # Rendered Markdown has no article wrappers. Anchors delimit turns; only
    # their initial identity paragraphs and separate disclosures are excluded.
    turns = []
    pending = False
    identity = True
    for node in root.children:
        if isinstance(node, str):
            if not node.strip():
                continue
        elif not node.text().strip() and any(child.tag == "a" and child.attrs.get("id", "").startswith("turn-") for child in node.walk()):
            pending = True
            continue
        elif pending and node.tag == "h3":
            turns.append((node.text(), []))
            pending, identity = False, True
            continue
        elif node.tag == "details":
            continue
        elif identity and node.tag == "p" and any(isinstance(child, Element) and child.tag == "strong" and child.text() in {"Turn:", "Time:", "Model:"} for child in node.children):
            continue
        if turns:
            identity = False
            if value := semantic_node(node):
                turns[-1][1].append(value)
    return [(role, tuple(body)) for role, body in turns if role != "Exported activity"]


def assert_visible_turn_parity(markdown: str, html: str) -> None:
    rendered = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    expected, actual = visible_turns(html), visible_turns(rendered)
    assert expected, "The acceptance sample must contain visible turns"
    assert actual == expected, "Visible turn order, text or Markdown formatting differs"


class RenderedSnapshot(HTMLParser):
    """Read inert markup; do not execute scripts or fetch referenced URLs."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.anchors: list[str] = []
        self.links: set[str] = set()
        self.code: list[str] = []
        self.summaries: list[str] = []
        self.headings: list[str] = []
        self.metadata: list[str] = []
        self.bodies: list[str] = []
        self.text: list[str] = []
        self._pre: list[str] | None = None
        self._summary: list[str] | None = None
        self._heading: list[str] | None = None
        self._metadata: list[str] | None = None
        self._body: list[str] | None = None
        self._body_depth = 0
        self._ignored = 0
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"head", "script", "style"}:
            self._ignored += 1
        if self._ignored:
            return
        identifier = attributes.get("id", "")
        if identifier.startswith(("turn-", "ref-source-", "ref-target-")):
            self.anchors.append(identifier)
        for key in ("href", "src"):
            if attributes.get(key):
                self.links.add(attributes[key])
        if tag == "pre":
            self._pre = []
        if tag == "summary":
            self._summary = []
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading = []
        if tag == "dd" or (tag == "p" and "turn-metadata" in attributes.get("class", "").split()):
            self._metadata = []
        if tag == "div":
            if self._body is not None:
                self._body_depth += 1
            elif "content" in attributes.get("class", "").split():
                self._body = []
                self._body_depth = 1
        if tag == "img":
            self.handle_data(attributes.get("alt", ""))

    def handle_endtag(self, tag):
        if tag in {"head", "script", "style"}:
            self._ignored -= 1
            return
        if self._ignored:
            return
        if tag == "pre" and self._pre is not None:
            self.code.append("".join(self._pre).rstrip("\n"))
            self._pre = None
        if tag == "summary" and self._summary is not None:
            self.summaries.append(normalized("".join(self._summary)))
            self._summary = None
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading is not None:
            self.headings.append(normalized(" ".join(self._heading)))
            self._heading = None
        if tag in {"dd", "p"} and self._metadata is not None:
            self.metadata.append(normalized(" ".join(self._metadata)))
            self._metadata = None
        if tag == "div" and self._body is not None:
            self._body_depth -= 1
            if not self._body_depth:
                self.bodies.append(normalized(" ".join(self._body)))
                self._body = None

    def handle_data(self, data):
        if self._ignored:
            return
        self.text.append(data)
        if self._pre is not None:
            self._pre.append(data)
        if self._summary is not None:
            self._summary.append(data)
        if self._heading is not None:
            self._heading.append(data)
        if self._metadata is not None:
            self._metadata.append(data)
        if self._body is not None:
            self._body.append(data)


def assert_rendered_parity(markdown: str, html: str) -> None:
    """Allow layout differences, but reject missing or reordered payloads."""
    rendered = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    assert_visible_turn_parity(markdown, html)
    md, standalone = RenderedSnapshot(rendered), RenderedSnapshot(html)
    assert md.anchors == standalone.anchors, "Turn/citation anchors differ or are reordered"
    assert md.summaries == standalone.summaries, "Activity/reference disclosures differ"
    assert md.headings == standalone.headings, "Roles or section headings differ"
    assert md.links == standalone.links, "Citation, context or artifact destinations differ"
    assert md.code == standalone.code, "Code/tool payloads differ or are reordered"
    md_text = normalized(" ".join(md.text))
    for index, body in enumerate(standalone.bodies):
        assert body in md_text, f"Turn body {index + 1} is missing or changed in rendered Markdown"
    for field in standalone.metadata:
        assert field in md_text, "Turn/activity identity, time, model or status differs"
    # Both formats can be wrong in the same way; test fixtures also assert
    # expected source text and links independently below.


@pytest.mark.parametrize("json_mode", ["readable", "pretty", "raw"])
@pytest.mark.parametrize("index", [False, True])
def test_formatter_semantic_parity(json_mode: str, index: bool) -> None:
    document = RenderDocument(
        title="Parity fixture", conversation_id="fixture", create_time=100,
        system_context=[SystemContextEntry(title="Profile", content="Preserved user preferences.")],
        turns=[
            RenderTurn(role="user", turn_id="question", timestamp=100, content="Please preserve **all** of this."),
            RenderTurn(role="assistant", turn_id="answer", timestamp=101,
                content="Answer:\n- First **point**\n- Second point\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```python\nprint(\"fixture\")\n```",
                metadata={"model_slug": "fixture-model", "context_citations": [{"attribution": "Past chat", "title": "Earlier chat", "url": "/c/earlier", "snippet": "Preserved excerpt."}]},
                tools_used=[
                    ToolActivityItem(category="tool_call", title="Tool call: terminal", turn_id="call", content='{"command":"printf \\"hello\\"\\n"}', metadata={"pair_id": "call", "tool_name": "terminal"}),
                    ToolActivityItem(category="tool_output", title="Result", turn_id="result", content='{"output":"first\\nsecond","exit_code":0}', metadata={"pair_id": "call", "tool_name": "terminal"}),
                    ToolActivityItem(category="reasoning", title="Reasoning", content="Planning **carefully**.\n\nKeep this explanation."),
                ],
                media_items=[MediaItem(kind="file", label="sample.csv", url="artifacts/sample.csv", metadata={"local_path": "artifacts/sample.csv", "mime_type": "text/csv", "table_rows": [["x", "y"], ["1", "2"]]})]),
        ],
    )
    original = deepcopy(document)
    config = {"timezone": "UTC", "turn_index": index, "tool_json": json_mode}
    markdown = MarkdownFormatter(config).format_document(document)
    html = HTMLFormatter(config).format_document(document)
    assert_rendered_parity(markdown, html)
    for output in (markdown, html):
        assert "fixture-model" in output and "Preserved user preferences." in output
        assert "artifacts/sample.csv" in output and "Preserved excerpt." in output
    assert document == original


@pytest.mark.parametrize("source", ["chatgpt", "work", "dots", "hermes"])
def test_source_adapter_output_parity(source: str) -> None:
    question, answer = "Preserved fixture question.", "Answer:\n- First point\n- Second point"
    if source in {"chatgpt", "work"}:
        raw = {"title": "Fixture", "conversation_origin": "tpp" if source == "work" else None, "mapping": {
            uid: {"id": uid, "parent": parent, "message": {"id": uid, "author": {"role": role}, "create_time": stamp, "content": {"content_type": "text", "parts": [text]}}}
            for uid, parent, role, stamp, text in [("q", None, "user", 100, question), ("a", "q", "assistant", 101, answer)]}}
    elif source == "dots":
        raw = {"format": "loggpt.dots", "format_version": 1, "title": "Fixture Dot", "conversation_id": "room", "create_time": 1793534400, "update_time": 1793534460, "source": {"kind": "dots", "scope": "main_timeline", "history_complete": True}, "dot": {"id": "dot"}, "room": {"id": "room", "members": [{"account_user_id": "human"}, {"account_user_id": "agent", "aeon_id": "dot"}]}, "messages": [
            {"id": uid, "role": "user", "account_user_id": sender, "created_at": stamp, "content": {"text": text}}
            for uid, sender, stamp, text in [("q", "human", "2026-11-01T12:00:00Z", question), ("a", "agent", "2026-11-01T12:01:00Z", answer)]]}
    else:
        raw = {"session_id": "fixture", "title": "Fixture Hermes", "exported_at": "2026-11-18T12:00:00Z", "message_count": 2, "messages": [
            {"id": stamp, "message_uid": uid, "session_id": "fixture", "role": role, "timestamp": stamp, "content": text}
            for uid, role, stamp, text in [("q", "user", 100, question), ("a", "assistant", 101, answer)]]}
    if source in {"chatgpt", "work"}:
        marker = "\ue200cite\ue202turn0search1\ue201"
        message = raw["mapping"]["a"]["message"]
        message["content"]["parts"][0] += "\n\nA cited claim." + marker
        message["metadata"] = {"content_references": [{"type": "grouped_webpages", "matched_text": marker, "items": [{"title": "Fixture source", "url": "https://example.org/source", "snippet": "Source excerpt."}]}]}
    conversation = Conversation.model_validate(parse_source(raw).conversation)
    try:
        DocumentContext.initialize(conversation=conversation)
        document = TurnProcessorV2().process_conversation(conversation)
    finally:
        DocumentContext.reset()
    config = {"timezone": "America/Chicago", "turn_index": True}
    markdown = MarkdownFormatter(config).format_document(document)
    html = HTMLFormatter(config).format_document(document)
    assert_rendered_parity(markdown, html)
    assert [turn.role for turn in document.turns] == ["user", "assistant"]
    for output in (markdown, html):
        assert question in output and "First point" in output and "Second point" in output
        if source in {"chatgpt", "work"}:
            assert "https://example.org/source" in output
            assert 'href="#ref-source-' in output or '](#ref-source-' in output
            assert 'href="#ref-target-' in output


@pytest.mark.parametrize("damage", ["body", "code", "link", "anchor", "summary", "role", "time", "model"])
def test_parity_check_detects_missing_content(damage: str) -> None:
    html = '<article class="block"><a id="turn-fixture"></a><h3>Assistant</h3><p class="turn-metadata">Time: 2026-11-01 12:00 UTC</p><p class="turn-metadata">Model: fixture-model</p><div class="content"><p>Keep this text.</p></div><details><summary>Tool call</summary><pre><code>result</code></pre></details><a href="artifacts/data.csv">data</a></article>'
    markdown = html
    assert_rendered_parity(markdown, html)
    replacements = {"body": ("Keep this text.", "Missing text."), "code": ("result", "lost result"), "link": ("artifacts/data.csv", "missing.csv"), "anchor": ("turn-fixture", "turn-missing"), "summary": ("Tool call", "Missing activity"), "role": ("Assistant", "User"), "time": ("12:00 UTC", "13:00 UTC"), "model": ("fixture-model", "wrong-model")}
    before, after = replacements[damage]
    with pytest.raises(AssertionError):
        assert_rendered_parity(markdown.replace(before, after), html)


@pytest.mark.parametrize("damage", ["bold", "italic", "inline-code", "list", "ordered-list", "table", "quote", "line-break", "link", "fenced-code", "turn-order"])
def test_visible_turn_formatting_cannot_silently_disappear(damage: str) -> None:
    content = "**Bold text** and *italic text* with `inline_code`.\n\n- First item\n  - Nested item\n- Last item\n\n1. First step\n2. Second step\n\nHard break  \ncontinued text with a [source](https://example.org/source).\n\n> Quoted text\n\n| Name | Value |\n| --- | --- |\n| item | 42 |\n\n```python\nprint(\"preserved\")\n```"
    document = RenderDocument(turns=[
        RenderTurn(role="user", turn_id="q", timestamp=1, content="Question"),
        RenderTurn(role="assistant", turn_id="a", timestamp=2, content=content),
    ])
    formatter = MarkdownFormatter({"timezone": "UTC"})
    markdown = formatter.format_document(document)
    html = HTMLFormatter({"timezone": "UTC"}).format_document(document)
    assert_visible_turn_parity(markdown, html)
    replacements = {"bold": ("**Bold text**", "Bold text"), "italic": ("*italic text*", "italic text"), "inline-code": ("`inline_code`", "inline_code"), "list": ("- First item", "First item"), "ordered-list": ("1. First step\n2. Second step", "First step\nSecond step"), "table": ("| --- | --- |", ""), "quote": ("> Quoted text", "Quoted text"), "line-break": ("Hard break\\\n", "Hard break\n"), "link": ("https://example.org/source", "https://example.org/wrong"), "fenced-code": ("```", "")}
    if damage == "turn-order":
        document.turns.reverse()
        damaged = formatter.format_document(document)
    else:
        damaged = markdown.replace(*replacements[damage])
    with pytest.raises(AssertionError, match="Visible turn"):
        assert_visible_turn_parity(damaged, html)


def test_visible_turn_acceptance_does_not_require_reasoning_or_tools() -> None:
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="answer", timestamp=1, content="Visible **answer**.\n\n- Keep this item", tools_used=[ToolActivityItem(category="reasoning", title="Reasoning", content="Extra exported activity.")]), RenderTurn(role="assistant", turn_id="orphan", timestamp=2, content="Extra standalone activity.", metadata={"activity_only": True})])
    html = HTMLFormatter().format_document(document)
    continuation = deepcopy(document)
    continuation.turns = continuation.turns[:1]
    continuation.turns[0].tools_used = []
    markdown = MarkdownFormatter().format_document(continuation)
    assert "Extra exported activity." in html and "Extra exported activity." not in markdown
    assert_visible_turn_parity(markdown, html)


def private_pairs() -> list[Path]:
    root = os.environ.get("EXTRACT_CHAT_REVIEW_DIR")
    if not root:
        return []
    pairs = sorted(Path(root).glob("*/*.html"))
    if not pairs:
        raise ValueError("EXTRACT_CHAT_REVIEW_DIR contains no extracted HTML/Markdown pairs")
    return pairs


@pytest.mark.parametrize("html_path", private_pairs())
def test_private_review_format_parity(html_path: Path) -> None:
    """Opt-in real samples stay outside Git; missing Markdown is a failure."""
    markdown_path = html_path.with_suffix(".md")
    assert markdown_path.is_file(), f"Missing Markdown companion: {markdown_path}"
    assert_visible_turn_parity(markdown_path.read_text(encoding="utf-8"), html_path.read_text(encoding="utf-8"))
