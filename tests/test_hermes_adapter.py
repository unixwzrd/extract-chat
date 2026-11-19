"""Hermes Desktop recognition, archival compaction semantics and inert activity."""

from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest

from extract_chat.adapters import parse_source
from extract_chat.chunking import ChunkOptions
from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.html_formatter import HTMLFormatter
from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.jobs import ConversionOptions, run_jobs
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation


@pytest.fixture
def hermes_export() -> dict:
    def message(uid: str, role: str, timestamp: float, content: str, **extra: object) -> dict:
        return {"id": int(timestamp), "message_uid": uid, "session_id": "hermes-fixture", "role": role, "timestamp": timestamp, "content": content, **extra}

    return {
        "exported_at": "2026-11-18T12:00:00Z", "session_id": "hermes-fixture", "title": "Hermes fixture", "session": None, "message_count": 5,
        "messages": [
            message("summary", "user", 200, "DUPLICATED COMPACTION SUMMARY", _compressed_summary=True, absorbed_message_uids='["question"]'),
            message("question", "user", 100, "Original archived question.", active=0, compacted=1),
            message("request", "assistant", 101, "Checking the fixture.", reasoning="Fixture thought.", reasoning_content="Fixture thought.", tool_calls=[{"id": "call-1", "call_id": "call-1", "type": "function", "function": {"name": "terminal", "arguments": '{"command":"printf fixture"}'}}]),
            message("result", "tool", 102, "<script>alert('not executable')</script>\n```\npayload", tool_call_id="call-1", tool_name="terminal"),
            message("reply", "assistant", 103, "Visible fixture reply."),
        ],
    }


def document(raw: dict):
    parsed = parse_source(raw)
    conversation = Conversation.model_validate(parsed.conversation)
    try:
        DocumentContext.initialize(conversation=conversation)
        return parsed, TurnProcessorV2().process_conversation(conversation)
    finally:
        DocumentContext.reset()


def test_hermes_normalizes_without_mutating_or_losing_native_records(hermes_export: dict) -> None:
    original = deepcopy(hermes_export)
    parsed, rendered = document(hermes_export)
    assert parsed.adapter == "hermes" and not parsed.diagnostics.has_warnings
    assert hermes_export == original
    assert parsed.conversation["conversation_id"] == "hermes-fixture"
    assert parsed.conversation["mapping"]["question"]["native_source"]["active"] == 0
    assert parsed.conversation["source_metadata"]["compaction_summaries"] == [original["messages"][0]]
    assert "not a native branch tree" in parsed.conversation["source_metadata"]["derived_mapping"]
    assert [turn.turn_id for turn in rendered.turns] == ["question", "request", "reply"]
    assert "1 compaction summary" in rendered.system_context[0].content
    assert all("DUPLICATED COMPACTION SUMMARY" not in turn.content for turn in rendered.turns)
    tools = rendered.turns[-1].tools_used
    assert [item.category for item in tools] == ["tool_call", "tool_output"]
    assert all(item.metadata["request_id"] == "call-1" for item in tools)
    assert [item.content for turn in rendered.turns for item in turn.tools_used if item.category == "reasoning" and item.content] == ["Fixture thought."]


def test_hermes_unmatched_result_is_preserved_and_not_a_fabricated_request(hermes_export: dict) -> None:
    hermes_export["messages"][2]["tool_calls"] = None
    _, rendered = document(hermes_export)
    assert "<summary>Tool result: terminal</summary>" in HTMLFormatter().format_document(rendered)
    assert not any(item.category == "tool_call" for turn in rendered.turns for item in turn.tools_used)


@pytest.mark.parametrize("change", ["count", "session", "uid", "id", "role", "timestamp", "content", "call_id", "call_owner", "date", "empty"])
def test_hermes_rejects_malformed_exports(hermes_export: dict, change: str) -> None:
    if change == "count":
        hermes_export["message_count"] += 1
    elif change == "session":
        hermes_export["messages"][1]["session_id"] = "another-session"
    elif change in {"uid", "id"}:
        field = "message_uid" if change == "uid" else "id"
        hermes_export["messages"][1][field] = hermes_export["messages"][0][field]
    elif change == "role":
        hermes_export["messages"][1]["role"] = "guess-this-author"
    elif change == "timestamp":
        hermes_export["messages"][1]["timestamp"] = float("nan")
    elif change == "content":
        hermes_export["messages"][1]["content"] = {"unsupported": "structured content"}
    elif change == "call_id":
        call = hermes_export["messages"][2]["tool_calls"][0]
        call.pop("id")
        call.pop("call_id")
    elif change == "call_owner":
        hermes_export["messages"][2]["role"] = "user"
    elif change == "date":
        hermes_export["exported_at"] = "2026-11-18T12:00:00"
    else:
        hermes_export["messages"] = []
        hermes_export["message_count"] = 0
    with pytest.raises(ValueError):
        parse_source(hermes_export)


def test_hermes_envelope_is_not_any_messages_list(hermes_export: dict) -> None:
    for raw in [{"messages": []}, {"session_id": "x", "messages": []}, {"format": "another-agent", **hermes_export}]:
        with pytest.raises(ValueError, match="Unsupported"):
            parse_source(raw)
    hermes_export["future_metadata"] = {"retained": True}
    parsed = parse_source(hermes_export)
    assert parsed.diagnostics.warnings[0].code == "unknown_hermes_key"
    assert parsed.conversation["source_metadata"]["envelope"]["future_metadata"] == {"retained": True}


def test_hermes_summary_only_and_tool_only_are_not_silently_empty(hermes_export: dict) -> None:
    summary_only = deepcopy(hermes_export)
    summary_only["messages"] = summary_only["messages"][:1]
    summary_only["message_count"] = 1
    _, rendered = document(summary_only)
    assert rendered.turns[0].role == "system"
    assert "original messages not present" in rendered.turns[0].content
    tool_only = deepcopy(hermes_export)
    tool_only["messages"] = tool_only["messages"][2:4]
    tool_only["messages"][0]["content"] = ""
    tool_only["message_count"] = 2
    _, rendered = document(tool_only)
    assert "no assistant reply text" in rendered.turns[-1].content
    assert any(item.category == "tool_output" for item in rendered.turns[-1].tools_used)


def test_hermes_collapsed_thoughts_arguments_and_results(hermes_export: dict) -> None:
    _, rendered = document(hermes_export)
    markdown = MarkdownFormatter().format_document(rendered)
    html = HTMLFormatter().format_document(rendered)
    for output in (markdown, html):
        assert "<summary>Thought</summary>" in output
        assert output.count("<summary>Tool call: terminal</summary>") == 1
        assert "Arguments" in output and "Result" in output
        assert "printf fixture" in output and "Visible fixture reply." in output
        assert "DUPLICATED COMPACTION SUMMARY" not in output
        assert "<details open" not in output and 'open="' not in output
    assert "&lt;script&gt;" in html and "<script>alert('not executable')</script>" not in html
    assert "````text" in markdown, "Payload fences cannot break out of their code block"


@pytest.mark.parametrize("archive", [False, True])
def test_hermes_managed_conversion_and_continuity(hermes_export: dict, tmp_path: Path, archive: bool) -> None:
    source = tmp_path / ("hermes.zip" if archive else "hermes.json")
    data = json.dumps(hermes_export)
    if archive:
        with zipfile.ZipFile(source, "w") as bundle:
            bundle.writestr("session.json", data)
    else:
        source.write_text(data, encoding="utf-8")
    original = source.read_bytes()
    result = run_jobs([source], ConversionOptions(output_dir=tmp_path / "results", chunk_options=ChunkOptions(max_bytes=4000)))[0]
    assert result["status"] == "completed", result
    output = Path(result["output"])
    assert len(list(output.glob("*.md"))) == 1 and len(list(output.glob("*.html"))) == 1
    assert list(output.glob("*-chunks/context-move-instructions.md"))
    assert list(output.glob("*-chunks/chunk-manifest.json"))
    assert source.read_bytes() == original
    assert not [path for path in tmp_path.rglob(".extract-chat-*") if path.is_dir()]
