from __future__ import annotations

import json
from pathlib import Path

from extract_chat.artifact_package import attach_local_artifacts, copy_artifact_package, load_artifact_entries, normalize_artifact_identifier
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


def test_work_artifacts_attach_by_sediment_id_and_workspace_link(tmp_path: Path) -> None:
    input_path = tmp_path / "work-chat.json"
    input_path.write_text("{}", encoding="utf-8")
    package = tmp_path / "work-chat"
    generated = package / "artifacts" / "generated"
    generated.mkdir(parents=True)
    (generated / "generated-image.png").write_bytes(b"png")
    (generated / "workspace-notes.md").write_text("# Notes\n", encoding="utf-8")
    manifest = {
        "format_version": 2,
        "artifacts": [
            {
                "canonical_id": "file-work-image",
                "asset_pointer": "sediment://file-work-image",
                "relative_path": "work-chat/artifacts/generated/generated-image.png",
                "original_filename": "generated-image.png",
                "detected_mime_type": "image/png",
                "origin": "generated",
                "download_status": "downloaded",
            },
            {
                "relative_path": "work-chat/artifacts/generated/workspace-notes.md",
                "original_filename": "workspace-notes.md",
                "source_url": "https://chatgpt.com/backend-api/estuary/content",
                "detected_mime_type": "text/markdown",
                "origin": "generated",
                "download_status": "downloaded",
            },
        ],
    }
    (package / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    document = RenderDocument(
        title="Work artifacts",
        turns=[
            RenderTurn(
                role="assistant",
                turn_id="turn-work",
                content="[Notes](sandbox:/workspace/scratch/fixture/workspace-notes.md)",
                media_items=[MediaItem(kind="asset_pointer", label="sediment://file-work-image")],
            )
        ],
    )
    output_path = tmp_path / "rendered" / "work-output.md"
    attach_local_artifacts(document=document, input_path=input_path, output_path=output_path)

    turn = document.turns[0]
    assert turn.media_items[0].metadata["canonical_id"] == "file-work-image"
    assert turn.media_items[0].url == "work-output/artifacts/generated/generated-image.png"
    assert turn.content == "[Notes](work-output/artifacts/generated/workspace-notes.md)"
    assert (tmp_path / "rendered" / "work-output" / "artifacts" / "generated" / "workspace-notes.md").exists()
    assert normalize_artifact_identifier("sediment://file-work-image") == "file-work-image"


def test_copy_artifact_package_skips_identical_materialized_file(tmp_path: Path) -> None:
    input_path = tmp_path / "source.json"
    input_path.write_text("{}", encoding="utf-8")
    source_file = tmp_path / "source" / "artifacts" / "generated" / "image.png"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"same-image")
    source_manifest = tmp_path / "source" / "artifact-manifest.json"
    source_manifest.write_text("{}", encoding="utf-8")

    destination = tmp_path / "rendered"
    target = destination / "artifacts" / "generated" / "image.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"same-image")

    result = copy_artifact_package(input_path, destination, force=False)
    assert result.artifact_copied == ()
    assert result.artifact_reused == (target,)
    assert result.artifact_total == 1
    assert result.metadata_copied == (destination / "artifact-manifest.json",)
    assert result.metadata_reused == ()
    assert result.metadata_total == 1
    assert target.read_bytes() == b"same-image"


def test_copy_artifact_package_refuses_different_existing_file(tmp_path: Path) -> None:
    input_path = tmp_path / "source.json"
    input_path.write_text("{}", encoding="utf-8")
    source_file = tmp_path / "source" / "artifacts" / "generated" / "image.png"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"new-image")

    destination = tmp_path / "rendered"
    target = destination / "artifacts" / "generated" / "image.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing-image")

    try:
        copy_artifact_package(input_path, destination, force=False)
    except RuntimeError as exc:
        assert "Refusing to overwrite existing artifact" in str(exc)
    else:
        raise AssertionError("Expected a different existing artifact to be protected")
    assert target.read_bytes() == b"existing-image"
