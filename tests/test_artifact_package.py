from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_same_stem_output_materializes_artifact_outside_temporary_source(tmp_path: Path) -> None:
    input_path = tmp_path / "temporary" / "chat.json"
    source_file = input_path.parent / "chat/artifacts/generated/file-note.txt"
    source_file.parent.mkdir(parents=True)
    input_path.write_text("{}", encoding="utf-8")
    source_file.write_text("preserved", encoding="utf-8")
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="t", media_items=[MediaItem(kind="file_id", label="file-note")])])
    output_path = tmp_path / "rendered/chat.md"
    attach_local_artifacts(document=document, input_path=input_path, output_path=output_path)
    assert document.turns[0].media_items[0].url == "chat/artifacts/generated/file-note.txt"
    assert (output_path.parent / document.turns[0].media_items[0].url).read_text() == "preserved"


def test_copy_package_updates_manifest_root_when_output_stem_changes(tmp_path: Path) -> None:
    input_path = tmp_path / "source" / "chat.1.json"
    source_file = input_path.parent / "chat.1/artifacts/generated/note.txt"
    source_file.parent.mkdir(parents=True)
    input_path.write_text("{}", encoding="utf-8")
    source_file.write_text("note", encoding="utf-8")
    manifest = {"artifacts": [{"relative_path": "chat.1/artifacts/generated/note.txt", "download_status": "downloaded"}]}
    (source_file.parents[2] / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    destination = tmp_path / "rendered/chat-1"
    copy_artifact_package(input_path, destination, force=False)
    copied = json.loads((destination / "artifact-manifest.json").read_text())
    entry = copied["artifacts"][0]
    assert entry["relative_path"] == "chat-1/artifacts/generated/note.txt"
    assert (destination.parent / entry["relative_path"]).read_text() == "note"
    assert entry["archive_relative_path"] == "chat.1/artifacts/generated/note.txt"


def test_adjacent_artifacts_without_manifest_and_no_unrelated_copies(tmp_path: Path) -> None:
    input_path = tmp_path / "chat.json"
    input_path.write_text("{}", encoding="utf-8")
    artifact = tmp_path / "artifacts/generated/note.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# Note", encoding="utf-8")
    (tmp_path / "private.txt").write_text("do not copy", encoding="utf-8")
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="t", content="[Notes](sandbox:/mnt/data/note.md)")])
    output = tmp_path / "output"
    attach_local_artifacts(document=document, input_path=input_path, output_path=output / "chat.md", artifact_destination=output)
    assert document.turns[0].content == "[Notes](artifacts/generated/note.md)"
    copy_artifact_package(input_path, output, force=False)
    assert (output / "artifacts/generated/note.md").read_bytes() == artifact.read_bytes()
    assert not (output / "private.txt").exists()
    assert not (output / "chat.json").exists()


def test_adjacent_artifact_symlink_cannot_read_outside_package(tmp_path: Path) -> None:
    root = tmp_path / "package"
    root.mkdir()
    input_path = root / "chat.json"
    input_path.write_text("{}", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    (root / "artifacts").mkdir()
    (root / "artifacts/escape.txt").symlink_to(outside)
    (root / "artifact-manifest.json").write_text(json.dumps({"artifacts": [{"canonical_id": "file-escape", "relative_path": "artifacts/escape.txt"}]}), encoding="utf-8")
    assert load_artifact_entries(input_path) == {}
    with pytest.raises(ValueError, match="Symlinked artifact"):
        copy_artifact_package(input_path, tmp_path / "output", force=False)


def test_failed_capture_is_explicit_and_never_leaves_a_working_sandbox_link(tmp_path: Path) -> None:
    input_path = tmp_path / "chat.json"
    input_path.write_text("{}", encoding="utf-8")
    manifest = {"artifacts": [{"original_filename": "missing.csv", "download_status": "failed", "failure_reason": "HTTP 404 from download endpoint"}]}
    (tmp_path / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    raw_manifest = (tmp_path / "artifact-manifest.json").read_bytes()
    locator = "sandbox:/workspace/scratch/session/missing.csv"
    code = f'`[code]({locator})`\n\n```text\n[code]({locator})\n```'
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="a", content=f'[Data]({locator})\n\n' + code)])
    attach_local_artifacts(document=document, input_path=input_path, output_path=tmp_path / "out/chat.html")
    turn = document.turns[0]
    assert "Data (not captured)" in turn.content
    assert code in turn.content, "Do not rewrite examples/recorded code as links"
    assert turn.media_items[0].metadata["unavailable_reason"] == "HTTP 404 from download endpoint"
    for formatter in (HTMLFormatter, MarkdownFormatter):
        output = formatter().format_document(document)
        assert "<summary>Artifacts</summary>" in output
        assert "Not captured" in output and "HTTP 404" in output
        assert f'href="{locator}"' not in output
    assert not list(tmp_path.rglob("missing.csv"))
    assert (tmp_path / "artifact-manifest.json").read_bytes() == raw_manifest


def test_captured_filename_with_spaces_unicode_and_parentheses_has_valid_url(tmp_path: Path) -> None:
    input_path = tmp_path / "chat.json"
    input_path.write_text("{}", encoding="utf-8")
    filename = "résumé (1).csv"
    artifact = tmp_path / "artifacts" / filename
    artifact.parent.mkdir()
    artifact.write_bytes(b"a,b\n1,2\n")
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="a", content='[Data](<sandbox:/mnt/data/résumé (1).csv>)')])
    output = tmp_path / "out/chat.html"
    attach_local_artifacts(document=document, input_path=input_path, output_path=output, artifact_destination=output.parent)
    assert document.turns[0].content == '[Data](artifacts/r%C3%A9sum%C3%A9%20%281%29.csv)'
    assert (output.parent / "artifacts" / filename).read_bytes() == artifact.read_bytes()
