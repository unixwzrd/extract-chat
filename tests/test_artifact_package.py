from __future__ import annotations

import json
from pathlib import Path

from extract_chat.artifact_package import attach_local_artifacts, load_artifact_entries
from extract_chat.formatters.html_formatter import HTMLFormatter
from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.schemas.render_models import MediaItem, RenderDocument, RenderTurn


def test_v2_manifest_attaches_and_renders_general_artifacts(tmp_path: Path) -> None:
    input_path = tmp_path / "chat.json"
    input_path.write_text("{}", encoding="utf-8")
    package = tmp_path / "chat"
    generated = package / "artifacts" / "generated"
    generated.mkdir(parents=True)
    (generated / "diagram.svg").write_text("<svg></svg>", encoding="utf-8")
    (generated / "narration.mp3").write_bytes(b"ID3audio")
    (generated / "results.tsv").write_text("name\tvalue\na\t1\n", encoding="utf-8")
    (generated / "mystery.bin").write_bytes(b"\x01\x02")
    artifacts = [
        ("file-svg", "diagram.svg", "image/svg+xml"),
        ("file-audio", "narration.mp3", "audio/mpeg"),
        ("file-table", "results.tsv", "text/tab-separated-values"),
        ("file-bin", "mystery.bin", "application/octet-stream"),
    ]
    manifest = {
        "format_version": 2,
        "artifacts": [
            {
                "canonical_id": identifier,
                "origin": "generated",
                "original_filename": filename,
                "saved_filename": filename,
                "relative_path": f"chat/artifacts/generated/{filename}",
                "detected_mime_type": mime_type,
                "download_status": "downloaded",
            }
            for identifier, filename, mime_type in artifacts
        ],
    }
    (package / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    document = RenderDocument(
        title="Artifacts",
        turns=[
            RenderTurn(
                role="assistant",
                turn_id="turn-1",
                media_items=[MediaItem(kind="file_id", label=identifier) for identifier, _, _ in artifacts],
            )
        ],
    )
    attach_local_artifacts(document=document, input_path=input_path, output_path=tmp_path / "chat.md")

    attached = document.turns[0].media_items
    assert attached[0].metadata["mime_type"] == "image/svg+xml"
    assert attached[2].metadata["table_rows"] == [["name", "value"], ["a", "1"]]
    markdown = MarkdownFormatter().format_conversation(document)
    html = HTMLFormatter().format_conversation(document)
    assert "![diagram.svg](chat/artifacts/generated/diagram.svg)" in markdown
    assert "<audio controls" in markdown
    assert "| name | value |" in markdown
    assert "[mystery.bin](chat/artifacts/generated/mystery.bin)" in markdown
    assert '<img src="chat/artifacts/generated/diagram.svg"' in html
    assert "<audio controls" in html
    assert "<table>" in html
    assert "mystery.bin" in html


def test_manifest_rejects_parent_traversal(tmp_path: Path) -> None:
    input_path = tmp_path / "chat.json"
    input_path.write_text("{}", encoding="utf-8")
    package = tmp_path / "chat"
    package.mkdir()
    (tmp_path / "secret.bin").write_bytes(b"secret")
    manifest = {
        "format_version": 2,
        "artifacts": [
            {
                "canonical_id": "file-secret",
                "relative_path": "../secret.bin",
                "download_status": "downloaded",
            }
        ],
    }
    (package / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert load_artifact_entries(input_path) == {}
