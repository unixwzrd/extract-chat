"""Source formats meet at one normalization boundary, including ZIP and continuity output."""

import json
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from extract_chat import cli
from extract_chat.adapters import ParsedSource, parse_source
from extract_chat.schemas.render_models import SchemaDiagnostics


@pytest.fixture
def dot_export() -> dict:
    return {
        "format": "loggpt.dots",
        "format_version": 1,
        "title": "Fixture Dot",
        "conversation_id": "room-1",
        "create_time": 1793534400,
        "update_time": 1793620800,
        "source": {"kind": "dots", "scope": "main_timeline", "history_complete": True, "excluded": ["linked_task_histories", "nested_reply_histories"]},
        "dot": {"id": "fixture-dot", "display_name": "Fixture Dot"},
        "room": {"id": "room-1", "members": [{"account_user_id": "human", "name": "Fixture User"}, {"account_user_id": "agent", "aeon_id": "fixture-dot", "name": "Fixture Dot"}]},
        "messages": [
            {"id": "answer", "role": "user", "account_user_id": "agent", "created_at": "2026-11-02T12:00:00Z", "content": {"text": "Here is the fixture answer.", "attachments": [
                {"type": "file", "file_id": "CalpicoFile_sample", "file": {"name": "note.md", "mime_type": "text/markdown"}},
                {"type": "thread", "thread_id": "11111111-1111-4111-8111-111111111111"},
            ]}},
            {"id": "question", "role": "user", "account_user_id": "human", "created_at": "2026-11-01T12:00:00Z", "content": {"text": "Please preserve this fixture question.", "attachments": []}},
        ],
    }


def test_dots_normalizes_sender_identity_without_mutating_source(dot_export: dict) -> None:
    original = deepcopy(dot_export)
    parsed = parse_source(dot_export)
    assert parsed.adapter == "dots"
    assert not parsed.diagnostics.has_warnings
    mapping = parsed.conversation["mapping"]
    assert list(mapping) == ["question", "answer"]
    assert mapping["question"]["message"]["author"]["role"] == "user"
    assert mapping["answer"]["message"]["author"]["role"] == "assistant"
    assert mapping["answer"]["native_source"]["role"] == "user"
    assert mapping["answer"]["parent"] == "question"
    assert "not a native ChatGPT branch tree" in parsed.conversation["source_metadata"]["derived_mapping"]
    assert parsed.conversation["mapping"]["answer"]["message"]["metadata"]["attachments"][0]["file_id"] == "CalpicoFile_sample"
    assert dot_export == original


@pytest.mark.parametrize("change", ["version", "sender", "duplicate", "incomplete", "timestamp", "room"])
def test_dots_rejects_unsafe_or_unsupported_input(dot_export: dict, change: str) -> None:
    if change == "version":
        dot_export["format_version"] = 2
    elif change == "sender":
        dot_export["messages"][0]["account_user_id"] = "unknown"
    elif change == "duplicate":
        dot_export["messages"].append(deepcopy(dot_export["messages"][0]))
    elif change == "incomplete":
        dot_export["source"]["history_complete"] = False
    elif change == "timestamp":
        dot_export["messages"][0]["created_at"] = "not-a-date"
    else:
        dot_export["conversation_id"] = "another-room"
    with pytest.raises(ValueError):
        parse_source(dot_export)


def test_dots_deletion_and_source_drift(dot_export: dict) -> None:
    dot_export["messages"][0]["deleted_at"] = "2026-11-03T12:00:00Z"
    dot_export["new_source_field"] = {"retained": True}
    parsed = parse_source(dot_export)
    message = parsed.conversation["mapping"]["answer"]["message"]
    assert message["content"]["parts"] == ["[Message deleted]"]
    assert message["metadata"]["attachments"] == []
    assert parsed.diagnostics.warnings[0].code == "unknown_dots_key"


def test_dots_attachment_only_record(dot_export: dict) -> None:
    dot_export["messages"][0]["content"]["text"] = None
    parsed = parse_source(dot_export)
    parts = parsed.conversation["mapping"]["answer"]["message"]["content"]["parts"]
    assert any("Linked Dot task" in part for part in parts)
    assert parsed.conversation["mapping"]["answer"]["native_source"]["content"]["text"] is None


def test_chatgpt_work_and_legacy_wrapper_keep_existing_path() -> None:
    raw = {"title": "Work fixture", "mapping": {"a": {"message": {"id": "a", "author": {"role": "assistant"}, "content": {"content_type": "multimodal_text", "parts": [{"generated_images": [{"file_id": "file-work"}]}]}}}}}
    original = deepcopy(raw)
    parsed = parse_source(raw)
    assert parsed.adapter == "chatgpt"
    assert parsed.conversation == raw == original
    wrapped = {"root_structure": {"fields": {key: {"value": value} for key, value in raw.items()}}}
    assert parse_source(wrapped).conversation == raw


def test_unknown_formats_require_their_own_adapter() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        parse_source({"messages": []})
    with pytest.raises(ValueError, match="Unsupported"):
        parse_source({"format": "unknown.agent", "mapping": {}})

    class ExampleAdapter:
        name = "example"

        def matches(self, raw: dict) -> bool:
            return raw.get("format") == "example.agent"

        def parse(self, raw: dict) -> ParsedSource:
            return ParsedSource(self.name, {"title": raw["title"], "mapping": {}}, SchemaDiagnostics())

    assert parse_source({"format": "example.agent", "title": "Example"}, adapters=(ExampleAdapter(),)).adapter == "example"


@pytest.mark.parametrize("extension", ["json", "zip", "lgpt"])
def test_dots_cli_renders_both_formats_and_continuity_bundle(dot_export: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extension: str) -> None:
    source = tmp_path / f"conversation.{extension}"
    if extension != "json":
        manifest = {"format_version": 2, "artifacts": [{"canonical_id": "CalpicoFile_sample", "relative_path": "fixture/artifacts/generated/note.md", "saved_filename": "note.md", "origin": "generated", "download_status": "downloaded"}]}
        with zipfile.ZipFile(source, "w") as bundle:
            bundle.writestr("fixture.json", json.dumps(dot_export))
            bundle.writestr("fixture/artifact-manifest.json", json.dumps(manifest))
            bundle.writestr("fixture/artifacts/generated/note.md", "# Local fixture artifact\n")
    else:
        source.write_text(json.dumps(dot_export), encoding="utf-8")
    original = source.read_bytes()
    destination = tmp_path / "output"
    monkeypatch.setattr("sys.argv", ["extract-chat", str(source), "--format", "both", "--chunk", "--output-dir", str(destination)])
    cli.main()
    transcripts = [path for path in destination.glob("*.md") if not path.name.endswith("schema-issue.md")]
    assert len(transcripts) == 1
    markdown = transcripts[0].read_text(encoding="utf-8")
    html_files = list(destination.glob("*.html"))
    assert len(html_files) == 1
    html = html_files[0].read_text(encoding="utf-8")
    for text in (markdown, html):
        assert "Please preserve this fixture question." in text
        assert "Here is the fixture answer." in text
        assert "Linked Dot task" in text
    assert markdown.index("Please preserve") < markdown.index("Here is")
    assert list(destination.glob("*-chunks/context-move-instructions.md"))
    assert list(destination.glob("*-chunks/chunk-manifest.json"))
    assert not list(destination.glob("*-schema-exception-report.json"))
    if extension != "json":
        assert "note.md" in markdown
        assert any(path.read_text(encoding="utf-8") == "# Local fixture artifact\n" for path in destination.rglob("note.md"))
        assert "](https://chatgpt.com/backend-api/messaging" not in markdown, "Artifact download links must resolve locally; provenance URLs may remain as metadata"
    assert source.read_bytes() == original
