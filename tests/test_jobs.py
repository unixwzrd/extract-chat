"""Private real archives are acceptance benchmarks; small fixtures cover errors."""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from extract_chat import cli
from extract_chat.artifact_package import load_artifact_entries
from extract_chat.chunking import ChunkOptions
from extract_chat.jobs import ConversionOptions, RESULT_MARKER, resolve_inputs, run_jobs


def source(root: Path, name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    result = root / name
    shutil.copyfile(Path(__file__).parent / "fixtures" / "packaging-smoke.json", result)
    return result


def test_literals_patterns_and_order(tmp_path: Path) -> None:
    literal = source(tmp_path, "[literal].json")
    other = source(tmp_path, "café.json")
    leading = source(tmp_path, "-leading.json")
    assert resolve_inputs([str(literal), str(tmp_path / "*.json"), str(other)]) == [literal, leading, other]
    nested = source(tmp_path / "nested", "more.json")
    assert nested in resolve_inputs([str(tmp_path / "**" / "*.json")])
    with pytest.raises(ValueError, match="no matches"):
        resolve_inputs([str(tmp_path / "missing*.zip")])
    with pytest.raises(ValueError, match="Unsupported"):
        resolve_inputs([str(tmp_path)])


def test_lgpt_batch_matches_zip_and_preserves_inputs(tmp_path: Path) -> None:
    conversation = source(tmp_path, "conversation.json")
    archive = tmp_path / "legacy.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(conversation, "conversation.json")
        bundle.writestr("artifacts/generated/example.bin", b"\x00\xfforiginal bytes")
    lgpt = tmp_path / "-café.LGPT"
    shutil.copyfile(archive, lgpt)
    original = lgpt.read_bytes()
    assert resolve_inputs([str(tmp_path / "*.LGPT"), str(lgpt)]) == [lgpt]
    records = run_jobs([archive, lgpt], ConversionOptions(output_dir=tmp_path / "out"))
    assert all(item["status"] == "completed" for item in records)
    legacy, custom = [Path(item["output"]) for item in records]
    for old in legacy.rglob("*"):
        if old.is_file():
            assert (custom / old.relative_to(legacy)).read_bytes() == old.read_bytes()
    assert lgpt.read_bytes() == archive.read_bytes() == original
    invalid = tmp_path / "not-an-archive.lgpt"
    invalid.write_text("Not a ZIP archive", encoding="utf-8")
    failed = run_jobs([invalid], ConversionOptions(output_dir=tmp_path / "invalid-output"))
    assert failed[0]["status"] == "failed" and not list((tmp_path / "invalid-output").iterdir())


def test_sequential_jobs_collision_and_chunks(tmp_path: Path) -> None:
    files = [source(tmp_path / "a", "same.json"), source(tmp_path / "b", "same.json")]
    options = ConversionOptions(output_dir=tmp_path / "out", chunk_options=ChunkOptions())
    records = run_jobs(files, options)
    assert [r["status"] for r in records] == ["completed", "completed"]
    assert [Path(r["output"]).name for r in records] == ["same", "same-2"]
    for record in records:
        folder = Path(record["output"])
        assert len(list(folder.glob("*.html"))) == 1
        assert len(list(folder.glob("*.md"))) == 1
        assert list(folder.glob("*-chunks/context-move-instructions.md"))
        assert (folder / RESULT_MARKER).is_file()
    assert run_jobs(files[:1], options)[0]["output"].endswith("same-3")


def test_force_only_managed_results(tmp_path: Path) -> None:
    file = source(tmp_path, "input.json")
    root = tmp_path / "out"
    run_jobs([file], ConversionOptions(output_dir=root))
    assert run_jobs([file], ConversionOptions(output_dir=root, force=True))[0]["status"] == "completed"
    extra = root / "input" / "my-notes.txt"
    extra.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="additional"):
        run_jobs([file], ConversionOptions(output_dir=root, force=True))
    assert extra.read_text(encoding="utf-8") == "keep"
    extra.unlink()
    (root / "input" / "unrelated-empty-directory").mkdir()
    with pytest.raises(ValueError, match="additional"):
        run_jobs([file], ConversionOptions(output_dir=root, force=True))


def test_bad_file_does_not_discard_other_results(tmp_path: Path) -> None:
    first = source(tmp_path, "first.json")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not JSON", encoding="utf-8")
    last = source(tmp_path, "last.json")
    records = run_jobs([first, invalid, last], ConversionOptions(output_dir=tmp_path / "out"))
    assert [r["status"] for r in records] == ["completed", "failed", "completed"]
    assert not (tmp_path / "out" / "invalid").exists()
    assert not list((tmp_path / "out").glob(".extract-chat-*"))


@pytest.mark.parametrize("stage", ["reading", "processing", "rendering", "chunking", "copying-artifacts", "copying-source", "finishing"])
def test_cancellation_preserves_completed_jobs(tmp_path: Path, stage: str) -> None:
    files = [source(tmp_path, f"input-{index}.json") for index in range(3)]
    def cancel(event: dict) -> None:
        if event.get("index") == 1 and event.get("stage") == stage:
            raise KeyboardInterrupt
    records = run_jobs(files, ConversionOptions(output_dir=tmp_path / "out", chunk_options=ChunkOptions()), cancel)
    assert [r["status"] for r in records] == ["completed", "cancelled", "cancelled"]
    assert (tmp_path / "out" / "input-0" / RESULT_MARKER).is_file()
    assert not (tmp_path / "out" / "input-1").exists()
    assert not list((tmp_path / "out").glob(".extract-chat-*"))


def test_cli_multi_and_structured_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    files = [source(tmp_path, "one.json"), source(tmp_path, "two.json")]
    monkeypatch.setattr("sys.argv", ["extract-chat", str(tmp_path / "*.json"), "--format", "both", "--progress-json", "--output-dir", str(tmp_path / "out")])
    cli.main()
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]["event"] == "summary"
    assert [item["status"] for item in events[-1]["results"]] == ["completed", "completed"]
    assert all(file.is_file() for file in files)


@pytest.mark.parametrize("flags", [["--output", "single.md"], ["--artifact-dir", "artifacts"], ["--batch-dir", "."]])
def test_cli_rejects_ambiguous_multi_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str]) -> None:
    files = [source(tmp_path, "one.json"), source(tmp_path, "two.json")]
    monkeypatch.setattr("sys.argv", ["extract-chat", *map(str, files), *flags])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_html_cannot_enable_markdown_chunks() -> None:
    with pytest.raises(ValueError, match="require Markdown"):
        ConversionOptions(format="html", chunk_options=ChunkOptions()).validate()


def test_explicit_managed_output_for_single_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    file = source(tmp_path, "only.json")
    monkeypatch.setattr("sys.argv", ["extract-chat", "--managed-output", "--output-dir", str(tmp_path / "out"), str(file)])
    cli.main()
    assert (tmp_path / "out" / "only" / RESULT_MARKER).is_file()
    assert not capsys.readouterr().out


def test_zip_cancellation_leaves_source_untouched(tmp_path: Path) -> None:
    original = source(tmp_path, "original.json")
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("conversation.json", original.read_bytes())
    before = archive.read_bytes()
    def cancel(event: dict) -> None:
        if event.get("stage") == "extracting":
            raise KeyboardInterrupt
    records = run_jobs([archive], ConversionOptions(output_dir=tmp_path / "out"), cancel)
    assert records[0]["status"] == "cancelled"
    assert archive.read_bytes() == before
    assert not list((tmp_path / "out").iterdir())


def test_inactive_css_does_not_block_markdown(tmp_path: Path) -> None:
    options = ConversionOptions(format="markdown", css_file=str(tmp_path / "missing.css"))
    options.validate()
    assert options.arguments(tmp_path).css_file is None


def test_display_options_reach_both_formats_and_chunks(tmp_path: Path) -> None:
    file = source(tmp_path, "display.json")
    options = ConversionOptions(output_dir=tmp_path / "out", timezone="UTC+05:30", turn_index=True, tool_json="raw", chunk_options=ChunkOptions())
    assert options.arguments(tmp_path).tool_json == "raw"
    record = run_jobs([file], options)[0]
    assert record["status"] == "completed", record
    output = Path(record["output"])
    for path in list(output.glob("*.md")) + list(output.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        assert "Conversation index" in text
        assert "UTC+05:30" in text
    chunks = list(output.glob("*-chunks/*-part-*.md"))
    assert chunks and all("UTC+05:30" in path.read_text(encoding="utf-8") for path in chunks)


def test_bad_timezone_fails_before_any_output(tmp_path: Path) -> None:
    file = source(tmp_path, "display.json")
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="Unknown time zone"):
        run_jobs([file], ConversionOptions(output_dir=output, timezone="Not/AZone"))
    assert not output.exists()


@pytest.mark.parametrize("archive", [False, True])
def test_result_keeps_exact_source_json_and_tracks_it_for_safe_overwrite(tmp_path: Path, archive: bool) -> None:
    original = source(tmp_path, "original.json")
    payload = original.read_bytes().replace(b"\n", b"\r\n")
    original.write_bytes(payload)
    input_file = original
    if archive:
        input_file = tmp_path / "archive.zip"
        with zipfile.ZipFile(input_file, "w") as bundle:
            bundle.writestr("nested/original.json", payload)
    before = input_file.read_bytes()
    options = ConversionOptions(output_dir=tmp_path / "out")
    record = run_jobs([input_file], options)[0]
    assert record["status"] == "completed", record
    result = Path(record["output"])
    assert (result / original.name).read_bytes() == payload, "Keep exact archive/input bytes and original filename"
    assert original.name in json.loads((result / RESULT_MARKER).read_text(encoding="utf-8"))["files"]
    assert not (result / "conversation-source.json").exists()
    assert run_jobs([input_file], ConversionOptions(output_dir=tmp_path / "out", force=True))[0]["status"] == "completed"
    assert (result / original.name).read_bytes() == payload
    assert input_file.read_bytes() == before


@pytest.mark.parametrize("archive", [False, True])
def test_flat_result_reextracts_retained_json_with_artifacts(tmp_path: Path, archive: bool) -> None:
    original = source(tmp_path / "inputs", "original.json")
    payload = json.loads(original.read_text(encoding="utf-8"))
    payload["mapping"]["answer"]["message"]["content"]["parts"] = ["[Notes](sandbox:/mnt/data/note.md)"]
    original.write_text(json.dumps(payload), encoding="utf-8")
    package = original.with_suffix("")
    artifact = package / "artifacts" / "generated" / "note.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"# Exact artifact\r\n")
    manifest = {"artifacts": [{"canonical_id": "file-note", "relative_path": "original/artifacts/generated/note.md", "original_filename": "note.md"}]}
    (package / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (package / "old-render.html").write_text("do not copy", encoding="utf-8")
    input_file = original
    if archive:
        input_file = tmp_path / "input.zip"
        with zipfile.ZipFile(input_file, "w") as bundle:
            bundle.write(original, original.name)
            bundle.write(artifact, "original/artifacts/generated/note.md")
            bundle.write(package / "artifact-manifest.json", "original/artifact-manifest.json")
    options = ConversionOptions(output_dir=tmp_path / "out", media_index=True, chunk_options=ChunkOptions())
    first = run_jobs([input_file], options)[0]
    assert first["status"] == "completed", first
    result = Path(first["output"])
    assert (result / "original.json").read_bytes() == original.read_bytes()
    assert (result / "artifacts/generated/note.md").read_bytes() == artifact.read_bytes()
    assert (result / "artifact-manifest.json").is_file()
    assert "file-note" in load_artifact_entries(result / "original.json")
    assert json.loads((result / "artifact-manifest.json").read_text(encoding="utf-8"))["artifacts"][0]["relative_path"] == "artifacts/generated/note.md"
    assert not (result / "original").exists()
    assert not list(result.rglob("old-render.html"))
    for path in [*result.glob("*.md"), *result.glob("*.html")]:
        assert "artifacts/generated/note.md" in path.read_text(encoding="utf-8")
    # Reprocess the retained JSON, not the original ZIP. No old transcripts,
    # chunks or sibling files should be copied as an artifact package.
    (result / "personal-notes.txt").write_text("private", encoding="utf-8")
    second = run_jobs([result / "original.json"], ConversionOptions(output_dir=tmp_path / "again"))[0]
    assert second["status"] == "completed", second
    rerun = Path(second["output"])
    assert (rerun / "original.json").read_bytes() == original.read_bytes()
    assert (rerun / "artifacts/generated/note.md").read_bytes() == artifact.read_bytes()
    assert not list(rerun.glob("*-chunks"))
    assert not (rerun / "personal-notes.txt").exists()
    assert not (rerun / "media-index.json").exists()
    for extension in ("md", "html"):
        assert next(rerun.glob(f"*.{extension}")).read_bytes() == next(result.glob(f"*.{extension}")).read_bytes()


def test_plain_json_does_not_create_empty_artifact_directories(tmp_path: Path) -> None:
    file = source(tmp_path, "plain.json")
    record = run_jobs([file], ConversionOptions(output_dir=tmp_path / "out"))[0]
    assert record["status"] == "completed", record
    assert not any(path.is_dir() for path in Path(record["output"]).iterdir())


def test_missing_artifact_warns_without_failing_or_creating_schema_report(tmp_path: Path) -> None:
    original = source(tmp_path, "original.json")
    payload = json.loads(original.read_text(encoding="utf-8"))
    payload["mapping"]["answer"]["message"]["content"]["parts"] = ["[Data](sandbox:/mnt/data/absent.csv)"]
    original.write_text(json.dumps(payload), encoding="utf-8")
    record = run_jobs([original], ConversionOptions(output_dir=tmp_path / "out"))[0]
    assert record["status"] == "completed", record
    assert record["warnings"] == 2, "Both render formats flag the unavailable source artifact"
    result = Path(record["output"])
    assert not list(result.glob("*schema-exception*"))
    assert "not captured" in next(result.glob("*.md")).read_text(encoding="utf-8")
