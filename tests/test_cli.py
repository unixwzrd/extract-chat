import json
import sys
import zipfile
from pathlib import Path
from subprocess import CompletedProcess

from extract_chat import cli
from extract_chat.processors.schema_diagnostics import analyze_raw_conversation
from extract_chat.schemas.render_models import SchemaDiagnostics, SchemaWarning
from tests.sample_data import SAMPLE_PATH, TURN_ID


def run_cli(arguments: list[str]) -> None:
    original = sys.argv
    try:
        sys.argv = arguments
        cli.main()
    finally:
        sys.argv = original


def test_chunk_help_separates_strategy_from_overlap_modes() -> None:
    help_text = cli.build_parser().format_help()

    assert "Select chunk boundaries independently of overlap" in help_text
    assert "--chunk-overlap-turns N" in help_text
    assert "--chunk-overlap-lines N" in help_text
    assert "--chunk-overlap-bytes BYTES" in help_text
    assert "--chunk-upload-batch-size FILES" in help_text
    assert "N is required when this option is used" in help_text
    assert "use 0 for no overlap" in help_text
    assert "If no overlap option is supplied" in help_text


def test_chunk_overlap_modes_are_mutually_exclusive(capsys) -> None:
    parser = cli.build_parser()

    try:
        parser.parse_args(["--chunk-overlap-lines", "10", "--chunk-overlap-bytes", "100"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected mutually exclusive overlap modes to stop argument parsing")

    assert "not allowed with argument" in capsys.readouterr().err


def test_cli_writes_generated_context_move_instructions(tmp_path: Path) -> None:
    output_path = tmp_path / "conversation.md"
    args = [
        "extract-chat",
        str(SAMPLE_PATH),
        "--output",
        str(output_path),
        "--chunk",
        "--chunk-upload-batch-size",
        "3",
    ]
    run_cli(args)

    instructions_path = tmp_path / "conversation-chunks" / "context-move-instructions.md"
    assert instructions_path.exists()
    instructions = instructions_path.read_text(encoding="utf-8")
    assert "up to 3 conversation chunks per batch" in instructions
    assert "Numbered conversation chunks:" in instructions


def test_cli_supports_jekyll_format(tmp_path: Path) -> None:
    output_dir = tmp_path / "jekyll"
    args = [
        "extract-chat",
        str(SAMPLE_PATH),
        "--format",
        "jekyll",
        "--jekyll-turn-id",
        TURN_ID,
        "--jekyll-base-slug",
        "2025-09-25-pa-paper",
        "--output",
        str(output_dir),
        "--force",
    ]
    run_cli(args)

    expected = output_dir / "2025-09-25-pa-paper-references.md"
    assert expected.exists()
    sections = list(output_dir.glob("2025-09-25-pa-paper-*.md"))
    assert sections, "Expected section markdown files to be written"


def test_cli_batch_validation_creates_outputs_and_reports(tmp_path: Path) -> None:
    source_dir = tmp_path / "source-json"
    source_dir.mkdir()

    valid_path = source_dir / "valid.json"
    valid_path.write_text(SAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    warning_payload = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    warning_payload["unexpected_export_shape"] = {"foo": "bar"}
    warning_path = source_dir / "warning.json"
    warning_path.write_text(json.dumps(warning_payload), encoding="utf-8")

    invalid_path = source_dir / "invalid.json"
    invalid_path.write_text('{"mapping": ', encoding="utf-8")

    output_root = tmp_path / "batch-run"
    args = [
        "extract-chat",
        "--batch-dir",
        str(source_dir),
        "--output",
        str(output_root),
        "--batch-formats",
        "both",
    ]
    run_cli(args)

    assert (output_root / "markdown").exists()
    assert (output_root / "html").exists()
    assert (output_root / "reports" / "summary.md").exists()
    assert (output_root / "reports" / "results.csv").exists()

    markdown_outputs = list((output_root / "markdown").glob("*.md"))
    html_outputs = list((output_root / "html").glob("*.html"))
    assert markdown_outputs, "Expected markdown outputs for successful files"
    assert html_outputs, "Expected html outputs for successful files"

    summary = (output_root / "reports" / "summary.md").read_text(encoding="utf-8")
    csv_report = (output_root / "reports" / "results.csv").read_text(encoding="utf-8")

    assert "Total files discovered: 3" in summary
    assert "Files with schema warnings" in summary
    assert "warning.json" in summary
    assert "invalid.json" in csv_report
    assert "failed" in csv_report
    assert "warning.json" in csv_report
    assert "unknown_top_level_key" in csv_report

    schema_reports = list(output_root.glob("**/*schema-exception-report.json"))
    assert schema_reports, "Expected schema exception reports for warning-producing files"
    schema_issue_bundles = list(output_root.glob("**/*schema-issue.md"))
    assert schema_issue_bundles, "Expected schema issue bundles for warning-producing files"


def test_cli_recovers_legacy_flat_and_role_only_messages(tmp_path: Path) -> None:
    legacy_payload = {
        "title": "Legacy Export",
        "create_time": 1676592000.0,
        "update_time": 1676592010.0,
        "current_node": "assistant-1",
        "mapping": {
            "root": {
                "id": "root",
                "children": ["system-flat"],
            },
            "system-flat": {
                "id": "system-flat",
                "parent": "root",
                "children": ["user-1"],
                "author": {"role": "system", "metadata": {}},
                "content": {"content_type": "text", "parts": [""]},
                "create_time": 1676592001.0,
                "recipient": "all",
                "metadata": {},
            },
            "user-1": {
                "id": "user-1",
                "parent": "system-flat",
                "children": ["assistant-1"],
                "message": {
                    "id": "user-1",
                    "role": "user",
                    "content": {"content_type": "text", "parts": ["Legacy user prompt"]},
                },
            },
            "assistant-1": {
                "id": "assistant-1",
                "parent": "user-1",
                "children": [],
                "message": {
                    "id": "assistant-1",
                    "author": {"role": "assistant", "metadata": {}},
                    "content": {"content_type": "text", "parts": ["Legacy assistant reply"]},
                    "create_time": 1676592002.0,
                    "recipient": "all",
                    "metadata": {},
                },
            },
        },
        "moderation_results": [],
    }
    input_path = tmp_path / "legacy.json"
    input_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    output_path = tmp_path / "legacy.md"
    args = [
        "extract-chat",
        str(input_path),
        "--format",
        "markdown",
        "--output",
        str(output_path),
        "--force",
    ]
    run_cli(args)

    rendered = output_path.read_text(encoding="utf-8")
    assert "Legacy user prompt" in rendered
    assert "Legacy assistant reply" in rendered

    schema_reports = list(tmp_path.glob("*schema-exception-report.json"))
    assert schema_reports, "Expected a schema exception report for legacy normalization"
    report_text = schema_reports[0].read_text(encoding="utf-8")
    assert "legacy_flat_turn" in report_text
    assert "legacy_message_role" in report_text
    assert "https://github.com/unixwzrd/extract-chat/issues/new?" in report_text
    issue_bundle = next(tmp_path.glob("*schema-issue.md"))
    issue_bundle_text = issue_bundle.read_text(encoding="utf-8")
    assert "## Schema Drift Report" in issue_bundle_text


def test_schema_diagnostics_accepts_common_newer_content_types() -> None:
    payload = {
        "title": "content types",
        "mapping": {
            "1": {
                "id": "1",
                "message": {
                    "id": "1",
                    "author": {"role": "tool", "metadata": {}},
                    "recipient": "all",
                    "metadata": {},
                    "content": {"content_type": "system_error", "text": "x"},
                },
            },
            "2": {
                "id": "2",
                "message": {
                    "id": "2",
                    "author": {"role": "tool", "metadata": {}},
                    "recipient": "all",
                    "metadata": {},
                    "content": {"content_type": "tether_quote", "text": "x"},
                },
            },
            "3": {
                "id": "3",
                "message": {
                    "id": "3",
                    "author": {"role": "tool", "metadata": {}},
                    "recipient": "all",
                    "metadata": {},
                    "content": {"content_type": "tether_browsing_display", "text": "x"},
                },
            },
            "4": {
                "id": "4",
                "message": {
                    "id": "4",
                    "author": {"role": "user", "metadata": {}},
                    "recipient": "all",
                    "metadata": {"is_user_system_message": True},
                    "content": {"content_type": "user_editable_context", "text": "x"},
                },
            },
            "5": {
                "id": "5",
                "message": {
                    "id": "5",
                    "author": {"role": "user", "metadata": {"real_author": "tool:app-pairing"}},
                    "recipient": "all",
                    "metadata": {"is_visually_hidden_from_conversation": True},
                    "content": {"content_type": "app_pairing_content", "text": "x"},
                },
            },
        },
    }

    diagnostics = analyze_raw_conversation(payload)
    codes = {warning.code for warning in diagnostics.warnings}
    assert "unknown_content_type" not in codes


def test_schema_diagnostics_accepts_chatgpt_work_top_level_fields() -> None:
    payload = {
        "title": "Work conversation",
        "mapping": {},
        "context_truncation_continuation": None,
        "is_study_mode": False,
        "is_temporary_chat": False,
    }
    diagnostics = analyze_raw_conversation(payload)
    assert "unknown_top_level_key" not in {warning.code for warning in diagnostics.warnings}


def test_cli_writes_media_inventory_when_requested(tmp_path: Path) -> None:
    payload = {
        "title": "Media Export",
        "mapping": {
            "root": {"id": "root", "children": ["user-1"]},
            "user-1": {
                "id": "user-1",
                "parent": "root",
                "children": [],
                "message": {
                    "id": "user-1",
                    "author": {"role": "user", "metadata": {}},
                    "recipient": "all",
                    "metadata": {},
                    "content": {
                        "content_type": "multimodal_text",
                        "parts": [{"asset_pointer": "file-service://asset-123", "url": "https://example.com/image.png"}],
                        "assets": [{"download_url": "https://example.com/file.pdf", "file_id": "file-123"}],
                    },
                },
            },
        },
    }
    input_path = tmp_path / "media.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path = tmp_path / "media.md"

    args = [
        "extract-chat",
        str(input_path),
        "--format",
        "markdown",
        "--output",
        str(output_path),
        "--media-index",
        "--force",
    ]
    run_cli(args)

    inventory_path = tmp_path / "media" / "media-index.json"
    assert inventory_path.exists()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert inventory["media_count"] >= 1
    assert any(item["media"].get("asset_pointer") == "file-service://asset-123" for item in inventory["items"])
    rendered = output_path.read_text(encoding="utf-8")
    assert "<summary>Media</summary>" in rendered
    assert "https://example.com/image.png" in rendered


def test_cli_prefers_local_media_bundle_links_when_present(tmp_path: Path) -> None:
    payload = {
        "title": "Media Bundle",
        "mapping": {
            "root": {"id": "root", "children": ["user-1"]},
            "user-1": {
                "id": "user-1",
                "parent": "root",
                "children": [],
                "message": {
                    "id": "user-1",
                    "author": {"role": "user", "metadata": {}},
                    "recipient": "all",
                    "metadata": {
                        "attachments": [
                            {
                                "id": "file_abc123",
                                "name": "test-image.png",
                            }
                        ]
                    },
                    "content": {
                        "content_type": "multimodal_text",
                        "parts": [
                            {
                                "asset_pointer": "file-service://file_abc123",
                                "url": "https://chatgpt.com/backend-api/estuary/content?id=file_abc123&sig=xyz",
                            }
                        ],
                    },
                },
            },
        },
    }
    input_path = tmp_path / "bundle.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    bundle_dir = tmp_path / "bundle"
    media_dir = bundle_dir / "media"
    media_dir.mkdir(parents=True)
    local_media = media_dir / "file_abc123.png"
    local_media.write_bytes(b"png-bytes")
    manifest = {
        "items": [
            {
                "canonical_id": "file_abc123",
                "saved_filename": "file_abc123.png",
                "relative_path": "media/file_abc123.png",
                "original_filename": "uploaded-image.png",
                "source_url": "https://chatgpt.com/backend-api/estuary/content?id=file_abc123&sig=xyz",
            }
        ]
    }
    (bundle_dir / "media-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    output_path = tmp_path / "rendered" / "bundle.md"
    args = [
        "extract-chat",
        str(input_path),
        "--format",
        "markdown",
        "--output",
        str(output_path),
        "--force",
    ]
    run_cli(args)

    rendered = output_path.read_text(encoding="utf-8")
    assert "![uploaded-image.png](../bundle/media/file_abc123.png)" in rendered
    assert "- Download image: [uploaded-image.png](../bundle/media/file_abc123.png)" in rendered
    assert "- File ID: `file_abc123`" in rendered
    assert "- Remote: `https://chatgpt.com/backend-api/estuary/content?id=file_abc123&sig=xyz`" in rendered


def test_cli_reads_plus_zip_and_reports_complete_artifact_package(tmp_path: Path, caplog) -> None:
    payload = {
        "title": "Plus Archive",
        "create_time": 1_700_000_000,
        "update_time": 1_700_086_400,
        "mapping": {
            "root": {"id": "root", "children": ["user-1"]},
            "user-1": {
                "id": "user-1", "parent": "root", "children": [],
                "message": {
                    "id": "message-1", "author": {"role": "user", "metadata": {}},
                    "recipient": "all", "metadata": {"attachments": [{"id": "file_test", "name": "upload.png"}]},
                    "content": {"content_type": "multimodal_text", "parts": [{"asset_pointer": "file-service://file_test"}]},
                },
            },
        },
    }
    archive_path = tmp_path / "plus.zip"
    manifest = {"artifacts": [{
        "canonical_id": "file_test", "relative_path": "plus/artifacts/uploaded/upload.png",
        "original_filename": "upload.png", "origin": "uploaded", "download_status": "downloaded",
    }]}
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("plus.json", json.dumps(payload))
        archive.writestr("plus/artifact-manifest.json", json.dumps(manifest))
        archive.writestr("plus/artifacts/uploaded/upload.png", b"png")

    destination = tmp_path / "out"
    run_cli(["extract-chat", str(archive_path), "--output-dir", str(destination), "--format", "both"])
    stem = "2023-11-14--2023-11-15--plus-archive"
    assert (destination / f"{stem}.md").exists()
    assert (destination / f"{stem}.html").exists()
    assert (destination / stem / "artifacts/uploaded/upload.png").read_bytes() == b"png"
    assert f"{stem}/artifacts/uploaded/upload.png" in (destination / f"{stem}.md").read_text()
    assert "Packaged 1 artifact file(s)" in caplog.text
    assert "0 copied, 1 already materialized" in caplog.text
    assert "1 package metadata file(s) also present" in caplog.text


def test_maybe_file_schema_issue_skips_duplicate(monkeypatch) -> None:
    diagnostics = SchemaDiagnostics(
        warnings=[
            SchemaWarning(
                code="legacy_message_role",
                path="$.mapping.x.message.role",
                message="Legacy message role field detected.",
                fallback_used=True,
            )
        ],
        content_types=["text"],
    )
    calls = []

    def fake_run(args, capture_output, text, check):  # type: ignore[no-untyped-def]
        calls.append(args)
        if args[:3] == ["gh", "issue", "list"]:
            return CompletedProcess(args, 0, stdout='[{"number": 12, "url": "https://github.com/unixwzrd/extract-chat/issues/12"}]', stderr="")
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    cli._maybe_file_schema_issue(
        diagnostics=diagnostics,
        input_path=Path("sample.json"),
        report_path=Path("sample-schema-exception-report.json"),
        repo="unixwzrd/extract-chat",
    )
    assert any(args[:3] == ["gh", "issue", "list"] for args in calls)
    assert not any(args[:3] == ["gh", "issue", "create"] for args in calls)
