"""Sequential, transactional conversion jobs shared by the CLI and native app."""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from extract_chat.archive import ARCHIVE_SUFFIXES, extract_archive
from extract_chat.chunking import ChunkOptions
from extract_chat.cli import convert_file
from extract_chat.progress import report, reporting
from extract_chat.display_time import resolve_timezone

RESULT_MARKER = ".extract-chat-result.json"


@dataclass(frozen=True)
class ConversionOptions:
    format: str = "both"
    output_dir: Path | None = None
    force: bool = False
    css_file: str | None = None
    emit_tsv: bool = True
    media_index: bool = False
    verbose: bool = False
    schema_warning_detail: str = "summary"
    chunk_options: ChunkOptions | None = None
    timezone: str = "local"
    turn_index: bool = False
    tool_json: str = "readable"

    def validate(self) -> None:
        resolve_timezone(self.timezone)
        if self.tool_json not in {"readable", "pretty", "raw"}:
            raise ValueError("Tool JSON display must be readable, pretty, or raw.")
        if self.format not in {"markdown", "html", "both"}:
            raise ValueError("Queued conversions support markdown, html, or both; use single-file mode for Jekyll.")
        if self.chunk_options:
            self.chunk_options.validate()
            if self.format == "html":
                raise ValueError("Continuity chunks require Markdown or both output formats.")
        if self.css_file and self.format != "markdown" and not Path(self.css_file).expanduser().is_file():
            raise ValueError(f"CSS file not found: {self.css_file}")
        if self.output_dir and self.output_dir.exists() and not self.output_dir.is_dir():
            raise ValueError(f"Output root is not a directory: {self.output_dir}")

    def arguments(self, destination: Path) -> argparse.Namespace:
        return argparse.Namespace(
            output=None, output_dir=str(destination), artifact_dir=None, flat_output=True,
            format=self.format, force=False, css_file=str(Path(self.css_file).expanduser().resolve()) if self.css_file and self.format != "markdown" else None,
            emit_tsv=self.emit_tsv, media_index=self.media_index, verbose=self.verbose,
            timezone=self.timezone, turn_index=self.turn_index,
            tool_json=self.tool_json,
            schema_warning_detail=self.schema_warning_detail, log_file=None,
            gh_file_schema_issue=False, gh_repo="unixwzrd/extract-chat",
            jekyll_turn_id=None, jekyll_base_slug=None, jekyll_layout="page", jekyll_reference_title="References",
        )


def resolve_inputs(values: list[str]) -> list[Path]:
    """Literal paths win over patterns; discover everything before writing."""
    result: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        expanded = os.path.expanduser(value)
        matches = [expanded] if Path(expanded).exists() else sorted(glob.glob(expanded, recursive="**" in expanded))
        if not matches:
            raise ValueError(f"Input or pattern has no matches: {value}")
        for match in matches:
            path = Path(match).resolve()
            if not path.is_file() or path.suffix.lower() not in ARCHIVE_SUFFIXES | {".json"}:
                raise ValueError(f"Unsupported input (expected JSON, LGPT or ZIP): {match}")
            if path not in seen:
                result.append(path)
                seen.add(path)
    return result


def validate_owned_result(destination: Path) -> None:
    """Only replace an intact managed result, never unrelated/additional files."""
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError(f"Refusing to replace an unmanaged output: {destination}")
    marker = destination / RESULT_MARKER
    if marker.is_symlink() or not marker.is_file():
        raise ValueError(f"Refusing to replace a folder without an Extract Chat result marker: {destination}")
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    current = {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file() and path != marker}
    directories = {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_dir()}
    if any(path.is_symlink() for path in destination.rglob("*")) or metadata.get("producer") != "extract-chat" or current != set(metadata.get("files", [])) or directories != set(metadata.get("directories", [])):
        raise ValueError(f"Refusing to replace a result with unrecognized or additional files: {destination}")


def plan_destinations(sources: list[Path], options: ConversionOptions) -> list[Path]:
    options.validate()
    reserved: set[str] = set()
    destinations = []
    for source in sources:
        root = options.output_dir.expanduser().resolve() if options.output_dir else source.parent
        destination = root / source.stem
        ordinal = 2
        if options.force and destination.exists():
            validate_owned_result(destination)
        while str(destination).casefold() in reserved or (destination.exists() and not options.force):
            destination = root / f"{source.stem}-{ordinal}"
            ordinal += 1
        if options.force and destination.exists():
            validate_owned_result(destination)
        if destination.is_symlink() or any(item.is_relative_to(destination.resolve()) for item in sources):
            raise ValueError(f"Output overlaps a source file: {destination}")
        reserved.add(str(destination).casefold())
        destinations.append(destination)
    return destinations


def run_jobs(sources: list[Path], options: ConversionOptions, sink: Callable[[dict[str, Any]], None] | None = None) -> list[dict[str, Any]]:
    destinations = plan_destinations(sources, options)
    records: list[dict[str, Any]] = []
    for index, (source, destination) in enumerate(zip(sources, destinations)):
        def emit(event: dict[str, Any]) -> None:
            if sink:
                sink({"protocol_version": 1, **event, "input": str(source), "index": index, "count": len(sources)})
        emit({"event": "started", "output": str(destination)})
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".extract-chat-", dir=destination.parent) as temporary:
                holder = Path(temporary)
                staged = holder / "result"
                with reporting(emit):
                    report("reading")
                    if source.suffix.lower() in ARCHIVE_SUFFIXES:
                        extracted = extract_archive(source, holder / "input")
                        input_json = extracted.json_path
                    else:
                        input_json = source
                    results = convert_file(str(input_json), options.arguments(staged), options.chunk_options)
                    failures = [item for item in results if item.status == "failed"]
                    if failures:
                        raise ValueError("; ".join(item.failure_message or "Conversion failed" for item in failures))
                    report("copying-source")
                    source_copy = staged / input_json.name
                    if source_copy.exists() or input_json.name == RESULT_MARKER:
                        raise ValueError(f"Source JSON name conflicts with a generated file: {input_json.name}")
                    shutil.copyfile(input_json, source_copy)
                    files = sorted(str(path.relative_to(staged)) for path in staged.rglob("*") if path.is_file())
                    directories = sorted(str(path.relative_to(staged)) for path in staged.rglob("*") if path.is_dir())
                    (staged / RESULT_MARKER).write_text(json.dumps({"producer": "extract-chat", "files": files, "directories": directories}, indent=2) + "\n", encoding="utf-8")
                    report("finishing")
                    if destination.exists():
                        if not options.force:
                            raise FileExistsError(f"Destination appeared while converting; retry: {destination}")
                        validate_owned_result(destination)
                        destination.rename(holder / "previous")
                    try:
                        staged.rename(destination)
                    except BaseException:
                        if (holder / "previous").exists():
                            (holder / "previous").rename(destination)
                        raise
            record = {"event": "finished", "status": "completed", "output": str(destination), "warnings": sum(item.warning_count for item in results)}
        except KeyboardInterrupt:
            record = {"event": "finished", "status": "cancelled"}
            records.append({**record, "input": str(source)})
            emit(record)
            for pending in sources[index + 1:]:
                records.append({"event": "finished", "status": "cancelled", "input": str(pending)})
            break
        except Exception as error:
            record = {"event": "finished", "status": "failed", "error": str(error)}
        records.append({**record, "input": str(source)})
        emit(record)
    if sink:
        sink({"protocol_version": 1, "event": "summary", "results": records})
    return records
