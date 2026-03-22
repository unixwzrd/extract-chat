#!/usr/bin/env python
"""Command line interface for extract_chat."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.parse import urlparse, parse_qs

from pydantic import ValidationError

from extract_chat import __version__
from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters import HTMLFormatter, MarkdownFormatter
from extract_chat.formatters.jekyll_formatter import JekyllTurnExporter
from extract_chat.processors.schema_diagnostics import analyze_raw_conversation
from extract_chat.processors.schema_normalization import normalize_raw_conversation
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation
from extract_chat.schemas.render_models import RenderDocument, SchemaDiagnostics

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s:%(lineno)d: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_GITHUB_ISSUES_URL = "https://github.com/unixwzrd/extract-chat/issues"
_GITHUB_NEW_ISSUE_URL = f"{_GITHUB_ISSUES_URL}/new"
_DEFAULT_GH_REPO = "unixwzrd/extract-chat"
_FILE_SERVICE_PREFIX = "file-service://"


@dataclass
class ExportResult:
    input_path: Path
    format_name: str
    status: str
    output_path: Path | None = None
    schema_report_path: Path | None = None
    warning_count: int = 0
    warning_codes: list[str] | None = None
    failure_type: str | None = None
    failure_message: str | None = None
    media_inventory_path: Path | None = None
    elapsed_seconds: float = 0.0


def _normalize_media_identifier(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            normalized = _normalize_media_identifier(item)
            if normalized:
                return normalized
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.startswith(_FILE_SERVICE_PREFIX):
        return text[len(_FILE_SERVICE_PREFIX):]
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        query_id = parse_qs(parsed.query).get("id", [None])[0]
        if query_id:
            return str(query_id)
    if text.startswith("file-") or text.startswith("file_"):
        return text
    return None


def _iter_media_identifiers(media_item: Any) -> list[str]:
    candidates: list[str] = []
    for value in (
        getattr(media_item, "label", None),
        getattr(media_item, "url", None),
        (getattr(media_item, "metadata", {}) or {}).get("value"),
        (getattr(media_item, "metadata", {}) or {}).get("canonical_id"),
        (getattr(media_item, "metadata", {}) or {}).get("asset_pointer"),
        (getattr(media_item, "metadata", {}) or {}).get("file_id"),
    ):
        normalized = _normalize_media_identifier(value)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _load_media_manifest_entries(input_path: Path) -> dict[str, dict[str, Any]]:
    base_dir = input_path.parent / input_path.stem
    media_dir = base_dir / "media"
    manifest_paths = [
        base_dir / "media-manifest.json",
        media_dir / "media-manifest.json",
    ]
    entries: dict[str, dict[str, Any]] = {}

    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Ignoring unreadable media manifest: %s", manifest_path)
            continue

        items = payload.get("items", []) if isinstance(payload, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            identifiers = [
                _normalize_media_identifier(item.get("canonical_id")),
                _normalize_media_identifier(item.get("file_id")),
                _normalize_media_identifier(item.get("asset_pointer")),
                _normalize_media_identifier(item.get("source_url")),
                _normalize_media_identifier(item.get("original_url")),
            ]
            relative_path = item.get("relative_path") or item.get("saved_path")
            if not relative_path:
                saved_filename = item.get("saved_filename") or item.get("filename")
                if saved_filename:
                    relative_path = f"media/{saved_filename}"
            if not relative_path:
                continue
            absolute_path = base_dir / str(relative_path)
            if not absolute_path.exists():
                continue
            for identifier in identifiers:
                if not identifier:
                    continue
                entries[identifier] = {
                    "canonical_id": identifier,
                    "absolute_path": absolute_path,
                    "relative_path": str(relative_path),
                    "display_name": item.get("original_filename") or item.get("saved_filename") or absolute_path.name,
                    "original_url": item.get("source_url") or item.get("original_url"),
                }

    if media_dir.exists():
        for media_file in media_dir.iterdir():
            if not media_file.is_file():
                continue
            identifier = _normalize_media_identifier(media_file.stem)
            if not identifier:
                identifier = media_file.stem
            entries.setdefault(
                identifier,
                {
                    "canonical_id": identifier,
                    "absolute_path": media_file,
                    "relative_path": str(Path("media") / media_file.name),
                    "display_name": media_file.name,
                    "original_url": None,
                },
            )

    return entries


def _attach_local_media_links(
    *,
    document: RenderDocument,
    input_path: Path,
    output_path: Path | None,
) -> None:
    manifest_entries = _load_media_manifest_entries(input_path)
    if not manifest_entries:
        return

    output_parent = output_path.parent if output_path is not None else input_path.parent
    for turn in document.turns:
        for item in turn.media_items:
            for identifier in _iter_media_identifiers(item):
                match = manifest_entries.get(identifier)
                if not match:
                    continue
                relative_link = os.path.relpath(match["absolute_path"], output_parent)
                if item.url:
                    item.metadata["original_url"] = item.url
                item.metadata["canonical_id"] = match["canonical_id"]
                item.metadata["local_path"] = relative_link
                item.metadata["display_name"] = match["display_name"]
                item.url = relative_link
                item.label = match["display_name"]
                break


def _slugify(value: str | None) -> str:
    if not value:
        return ""
    slug = value.lower()
    slug = _SLUG_CLEAN_RE.sub("-", slug)
    return slug.strip("-")


def _maybe_unwrap_structure_analysis(raw_text: str) -> str:
    try:
        obj = json.loads(raw_text)
        if isinstance(obj, dict) and "root_structure" in obj:
            rs = obj.get("root_structure") or {}
            fields = (rs.get("fields") or {}) if isinstance(rs, dict) else {}
            flat = {}
            for key, value in fields.items():
                if isinstance(value, dict) and "value" in value:
                    flat[key] = value["value"]
            if "mapping" in flat and isinstance(flat["mapping"], dict):
                return json.dumps(flat)
    except Exception:
        pass
    return raw_text


def _format_schema_issue_body(
    *,
    diagnostics: SchemaDiagnostics,
    input_path: Path | None = None,
    report_path: Path | None = None,
) -> str:
    warning_codes = sorted({warning.code for warning in diagnostics.warnings})
    signature = _schema_signature(diagnostics)
    body_lines = [
        "## Schema Drift Report",
        "",
        f"- schema signature: `{signature}`",
        f"- extract-chat version: `{__version__}`",
        f"- warning codes: `{', '.join(warning_codes) or 'none'}`",
        f"- content types: `{', '.join(diagnostics.content_types) or 'none'}`",
        f"- unknown top-level keys: `{', '.join(diagnostics.unknown_top_level_keys) or 'none'}`",
    ]
    if input_path is not None:
        body_lines.append(f"- source file: `{input_path.name}`")
    if report_path is not None:
        body_lines.append(f"- schema report path: `{report_path}`")
    body_lines.extend(
        [
            "",
            "## What Happened",
            "",
            "Describe the rendering problem or parse failure here.",
            "",
            "## Attachments",
            "",
            "- Attach the generated schema exception report.",
            "- Attach a redacted JSON sample if possible.",
        ]
    )
    return "\n".join(body_lines)


def _schema_signature(diagnostics: SchemaDiagnostics) -> str:
    payload = {
        "warning_codes": sorted({warning.code for warning in diagnostics.warnings}),
        "content_types": sorted(diagnostics.content_types),
        "unknown_top_level_keys": sorted(diagnostics.unknown_top_level_keys),
    }
    return sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _build_schema_issue_url(
    *,
    diagnostics: SchemaDiagnostics,
    input_path: Path | None = None,
    report_path: Path | None = None,
) -> str:
    warning_codes = sorted({warning.code for warning in diagnostics.warnings})
    title_codes = ", ".join(warning_codes[:3]) if warning_codes else "schema-drift"
    title = f"Schema drift: {title_codes}"
    body = _format_schema_issue_body(diagnostics=diagnostics, input_path=input_path, report_path=report_path)
    return f"{_GITHUB_NEW_ISSUE_URL}?{urlencode({'title': title, 'body': body})}"


def _emit_schema_warnings(
    diagnostics: SchemaDiagnostics,
    *,
    input_path: Path,
    detail: str,
) -> None:
    if detail == "full":
        for warning in diagnostics.warnings:
            logger.warning(
                "Schema warning [%s] at %s%s: %s",
                warning.code,
                warning.path,
                f" (turn {warning.turn_id})" if warning.turn_id else "",
                warning.message,
            )
    if diagnostics.warnings:
        issue_url = _build_schema_issue_url(diagnostics=diagnostics, input_path=input_path)
        codes = ", ".join(sorted({warning.code for warning in diagnostics.warnings}))
        logger.warning(
            "Schema drift was detected. Export continued with fallback handling where possible. "
            "Warning codes: %s. Please open a GitHub issue and attach the generated schema exception report plus a redacted sample JSON when possible. "
            "Issue link: %s",
            codes or "none",
            issue_url,
        )


def _schema_report_path(
    *,
    output_path: Path | None,
    output_dir: Path | None,
    input_file: str,
    fmt: str,
) -> Path:
    base_name = Path(input_file).stem
    if fmt == "jekyll" and output_dir is not None:
        return output_dir / f"{base_name}-schema-exception-report.json"
    if output_path is not None:
        parent = output_path.parent if output_path.suffix else output_path
        return parent / f"{base_name}-schema-exception-report.json"
    return Path(f"{base_name}-schema-exception-report.json")


def _write_schema_report(
    *,
    diagnostics: SchemaDiagnostics,
    destination: Path,
    conversation: Conversation | None,
    input_path: Path | None,
) -> None:
    issue_url = _build_schema_issue_url(diagnostics=diagnostics, input_path=input_path, report_path=destination)
    issue_body = _format_schema_issue_body(diagnostics=diagnostics, input_path=input_path, report_path=destination)
    issue_title = f"Schema drift: {', '.join(sorted({warning.code for warning in diagnostics.warnings})[:3]) or 'schema-drift'}"
    payload = {
        "extract_chat_version": __version__,
        "conversation_id": getattr(conversation, "conversation_id", None) if conversation else None,
        "content_types": diagnostics.content_types,
        "unknown_top_level_keys": diagnostics.unknown_top_level_keys,
        "warnings": [warning.model_dump() for warning in diagnostics.warnings],
        "issue_url": issue_url,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "guidance": (
            "Open a GitHub issue and attach this report with a redacted JSON sample "
            f"if you want this schema variation supported in a later patch: {issue_url}"
        ),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    issue_bundle_path = destination.with_name(destination.name.replace("-schema-exception-report.json", "-schema-issue.md"))
    issue_bundle_path.write_text(issue_body.rstrip() + "\n", encoding="utf-8")
    logger.warning("Wrote schema exception report to: %s", destination)
    logger.warning("Wrote schema issue bundle to: %s", issue_bundle_path)
    logger.warning("Open a prefilled schema issue here: %s", issue_url)


def _maybe_file_schema_issue(
    *,
    diagnostics: SchemaDiagnostics,
    input_path: Path,
    report_path: Path | None,
    repo: str,
) -> None:
    if not diagnostics.warnings:
        return
    signature = _schema_signature(diagnostics)
    search_term = f'"schema signature: `{signature}`" in:body state:open'
    try:
        search = subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--search", search_term, "--json", "number,title,url"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        logger.warning("`gh` is not installed; skipping automatic schema issue filing.")
        return
    except subprocess.CalledProcessError as exc:
        logger.warning("Unable to query GitHub issues with `gh`; skipping automatic schema issue filing: %s", exc.stderr.strip() or exc)
        return

    existing = json.loads(search.stdout or "[]")
    if existing:
        issue = existing[0]
        logger.warning(
            "A matching schema issue already exists for signature %s: #%s %s",
            signature,
            issue.get("number"),
            issue.get("url"),
        )
        return

    title = f"Schema drift: {', '.join(sorted({warning.code for warning in diagnostics.warnings})[:3]) or 'schema-drift'}"
    body = _format_schema_issue_body(diagnostics=diagnostics, input_path=input_path, report_path=report_path)
    try:
        created = subprocess.run(
            ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body, "--label", "schema-drift"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("Unable to create GitHub issue with `gh`: %s", exc.stderr.strip() or exc)
        return

    logger.warning("Created schema issue for signature %s: %s", signature, created.stdout.strip())


def _configure_logging(*, verbose: bool, log_file: str | None) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if log_file:
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(log_file):
                return
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(root_logger.level)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d: %(message)s"))
        root_logger.addHandler(fh)


def _iter_media_candidates(value: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(value, dict):
        media_keys = (
            "url",
            "content_url",
            "thumbnail_url",
            "image_url",
            "image_urls",
            "download_url",
            "asset_pointer",
            "file_id",
            "audio_asset_pointer",
        )
        matched = {key: value.get(key) for key in media_keys if key in value and value.get(key)}
        if matched:
            candidates.append(matched)
        for child in value.values():
            candidates.extend(_iter_media_candidates(child))
    elif isinstance(value, list):
        for item in value:
            candidates.extend(_iter_media_candidates(item))
    return candidates


def _collect_media_inventory(conversation: Conversation) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str, str]] = set()
    for turn_id, turn in getattr(conversation, "mapping", {}).items():
        message = getattr(turn, "message", None)
        if not message:
            continue
        role = getattr(getattr(message, "author", None), "role", None)
        content = getattr(message, "content", None)
        content_type = getattr(content, "content_type", None)
        payloads: list[Any] = []
        if content is not None and hasattr(content, "model_dump"):
            payloads.append(content.model_dump())
        metadata = getattr(message, "metadata", None)
        if isinstance(metadata, dict):
            payloads.append(metadata)
        parts = getattr(content, "parts", None)
        if isinstance(parts, list):
            payloads.append(parts)
        for payload in payloads:
            for candidate in _iter_media_candidates(payload):
                normalized = json.dumps(candidate, sort_keys=True, default=str)
                key = (getattr(message, "id", None), str(turn_id), normalized)
                if key in seen:
                    continue
                seen.add(key)
                inventory.append(
                    {
                        "turn_id": str(turn_id),
                        "message_id": getattr(message, "id", None),
                        "role": role,
                        "content_type": content_type,
                        "media": candidate,
                    }
                )
    return inventory


def _write_media_inventory(
    *,
    conversation: Conversation,
    input_path: Path,
    output_path: Path | None,
    output_dir: Path | None,
    format_name: str,
) -> Path | None:
    inventory = _collect_media_inventory(conversation)
    if not inventory:
        return None
    if format_name == "jekyll" and output_dir is not None:
        base_dir = output_dir / input_path.stem
    elif output_path is not None:
        base_dir = output_path.parent / input_path.stem
    else:
        base_dir = input_path.parent / input_path.stem
    base_dir.mkdir(parents=True, exist_ok=True)
    destination = base_dir / "media-index.json"
    payload = {
        "conversation_title": getattr(conversation, "title", None),
        "conversation_id": getattr(conversation, "conversation_id", None),
        "source_file": input_path.name,
        "media_count": len(inventory),
        "items": inventory,
    }
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote media inventory to: %s", destination)
    return destination


def _load_conversation(
    input_file: str,
    *,
    verbose: bool,
    schema_warning_detail: str,
) -> tuple[Conversation, SchemaDiagnostics]:
    with open(input_file, "r", encoding="utf-8") as handle:
        raw_text = handle.read()
    raw_text = _maybe_unwrap_structure_analysis(raw_text)
    raw_obj = json.loads(raw_text)
    diagnostics = analyze_raw_conversation(raw_obj)
    raw_obj = normalize_raw_conversation(raw_obj, diagnostics)
    _emit_schema_warnings(diagnostics, input_path=Path(input_file), detail=schema_warning_detail)

    try:
        conversation = Conversation.model_validate(raw_obj)
    except ValidationError as exc:
        raise RuntimeError(
            "The JSON could not be parsed into a usable conversation. "
            f"Please open a GitHub issue and attach a redacted sample or schema exception report: "
            f"{_build_schema_issue_url(diagnostics=diagnostics, input_path=Path(input_file))}"
        ) from exc

    if verbose:
        os.environ["EXTRACT_CHAT_DEBUG"] = "1"
    return conversation, diagnostics


def _resolve_single_output_path(input_file: str, output: str | None, format_name: str) -> Path:
    base_name = Path(input_file).stem
    ext = "md" if format_name == "markdown" else "html"
    output_file = output or f"{base_name}.{ext}"
    output_path = Path(output_file).expanduser()
    if output_path.exists() and output_path.is_dir():
        output_path = output_path / f"{base_name}.{ext}"
        logger.info("Output path is a directory; writing to %s inside it.", output_path)
    return output_path


def export_file(
    *,
    input_file: str,
    format_name: str,
    output: str | None,
    css_file: str | None,
    verbose: bool,
    force: bool,
    log_file: str | None = None,
    schema_warning_detail: str = "summary",
    media_index: bool = False,
    gh_file_schema_issue: bool = False,
    gh_repo: str = _DEFAULT_GH_REPO,
    jekyll_turn_id: str | None = None,
    jekyll_base_slug: str | None = None,
    jekyll_layout: str = "page",
    jekyll_reference_title: str = "References",
) -> ExportResult:
    start = time.perf_counter()
    input_path = Path(input_file)
    warning_codes: list[str] = []

    try:
        _configure_logging(verbose=verbose, log_file=log_file)
        conversation, diagnostics = _load_conversation(
            input_file,
            verbose=verbose,
            schema_warning_detail=schema_warning_detail,
        )
        warning_codes = [warning.code for warning in diagnostics.warnings]
        media_inventory_path: Path | None = None

        DocumentContext.initialize(conversation=conversation, verbose=verbose)
        try:
            if format_name == "jekyll":
                turn_id = jekyll_turn_id
                if not turn_id:
                    raise RuntimeError("--jekyll-turn-id is required when using --format jekyll")

                base_slug = jekyll_base_slug or _slugify(conversation.title)
                if not base_slug:
                    raise RuntimeError("Provide --jekyll-base-slug or ensure the conversation has a title to derive one.")

                output_dir = Path(output) if output else Path(base_slug)
                output_dir = output_dir.expanduser().resolve()
                if output_dir.exists() and not output_dir.is_dir():
                    raise RuntimeError(f"Output path must be a directory for Jekyll exports: {output_dir}")

                exporter = JekyllTurnExporter(base_slug=base_slug, layout=jekyll_layout)
                sections, references_page = exporter.export_turn(
                    conversation=conversation,
                    turn_id=turn_id,
                    reference_page_title=jekyll_reference_title,
                    audit_dir=output_dir,
                )
                all_pages = sections + [references_page]
                if not force:
                    for page in all_pages:
                        destination = output_dir / page.filename
                        if destination.exists():
                            raise RuntimeError(f"Refusing to overwrite existing file: {destination} (use --force)")

                output_dir.mkdir(parents=True, exist_ok=True)
                for page in all_pages:
                    destination = output_dir / page.filename
                    destination.write_text(page.content, encoding="utf-8")
                    logger.info("Wrote %s", destination)

                schema_report_path = None
                if diagnostics.has_warnings:
                    schema_report_path = _schema_report_path(
                        output_path=None,
                        output_dir=output_dir,
                        input_file=input_file,
                        fmt=format_name,
                    )
                    _write_schema_report(
                        diagnostics=diagnostics,
                        destination=schema_report_path,
                        conversation=conversation,
                        input_path=input_path,
                    )
                    if gh_file_schema_issue:
                        _maybe_file_schema_issue(
                            diagnostics=diagnostics,
                            input_path=input_path,
                            report_path=schema_report_path,
                            repo=gh_repo,
                        )
                if media_index:
                    media_inventory_path = _write_media_inventory(
                        conversation=conversation,
                        input_path=input_path,
                        output_path=None,
                        output_dir=output_dir,
                        format_name=format_name,
                    )

                return ExportResult(
                    input_path=input_path,
                    format_name=format_name,
                    status="success_with_warnings" if diagnostics.has_warnings else "success",
                    output_path=output_dir,
                    schema_report_path=schema_report_path,
                    warning_count=len(diagnostics.warnings),
                    warning_codes=warning_codes,
                    media_inventory_path=media_inventory_path,
                    elapsed_seconds=time.perf_counter() - start,
                )

            processor = TurnProcessorV2()
            document: RenderDocument = processor.process_conversation(conversation)
            document.schema_diagnostics = diagnostics

            formatter = HTMLFormatter({"css_file": css_file, "verbose": verbose}) if format_name == "html" else MarkdownFormatter({"verbose": verbose})
            output_path = _resolve_single_output_path(input_file, output, format_name)
            _attach_local_media_links(document=document, input_path=input_path, output_path=output_path)

            if output_path.exists() and output_path.is_dir():
                raise RuntimeError(f"Output path must be a file for markdown/html output. Got directory: {output_path}")
            if output_path.exists() and not force:
                raise RuntimeError(f"Refusing to overwrite existing file: {output_path} (use --force)")

            output_content = formatter.format_conversation(document)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_content, encoding="utf-8")
            logger.info("Wrote %s", output_path)

            schema_report_path = None
            if diagnostics.has_warnings:
                schema_report_path = _schema_report_path(
                    output_path=output_path,
                    output_dir=None,
                    input_file=input_file,
                    fmt=format_name,
                )
                _write_schema_report(
                    diagnostics=diagnostics,
                    destination=schema_report_path,
                    conversation=conversation,
                    input_path=input_path,
                )
                if gh_file_schema_issue:
                    _maybe_file_schema_issue(
                        diagnostics=diagnostics,
                        input_path=input_path,
                        report_path=schema_report_path,
                        repo=gh_repo,
                    )
            if media_index:
                media_inventory_path = _write_media_inventory(
                    conversation=conversation,
                    input_path=input_path,
                    output_path=output_path,
                    output_dir=None,
                    format_name=format_name,
                )

            return ExportResult(
                input_path=input_path,
                format_name=format_name,
                status="success_with_warnings" if diagnostics.has_warnings else "success",
                output_path=output_path,
                schema_report_path=schema_report_path,
                warning_count=len(diagnostics.warnings),
                warning_codes=warning_codes,
                media_inventory_path=media_inventory_path,
                elapsed_seconds=time.perf_counter() - start,
            )
        finally:
            DocumentContext.reset()
    except Exception as exc:
        logger.error("Error processing %s (%s): %s", input_file, format_name, exc)
        return ExportResult(
            input_path=input_path,
            format_name=format_name,
            status="failed",
            warning_count=len(warning_codes),
            warning_codes=warning_codes,
            failure_type=exc.__class__.__name__,
            failure_message=str(exc),
            elapsed_seconds=time.perf_counter() - start,
        )


def _default_batch_output_root() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("tmp") / f"batch-validate-{stamp}"


def _ensure_safe_batch_output(source_dir: Path, output_root: Path) -> Path:
    source_resolved = source_dir.resolve()
    output_resolved = output_root.expanduser().resolve()
    if os.path.commonpath([str(source_resolved), str(output_resolved)]) == str(source_resolved):
        raise RuntimeError("Batch output root must not be inside the source JSON directory or its symlink target.")
    return output_resolved


def _discover_json_files(batch_dir: Path) -> list[Path]:
    return sorted(
        path for path in batch_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    )


def _write_batch_reports(records: list[dict[str, Any]], reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = reports_dir / "results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_path",
                "markdown_status",
                "html_status",
                "warning_count",
                "warning_codes",
                "schema_report_paths",
                "failure_type",
                "failure_message",
                "markdown_output",
                "html_output",
                "elapsed_seconds",
            ],
        )
        writer.writeheader()
        writer.writerows(records)

    warning_counter: Counter[str] = Counter()
    failure_counter: Counter[str] = Counter()
    for record in records:
        for code in filter(None, str(record["warning_codes"]).split("|")):
            warning_counter[code] += 1
        if record["failure_type"]:
            failure_counter[str(record["failure_type"])] += 1

    markdown_successes = sum(1 for record in records if str(record["markdown_status"]).startswith("success"))
    markdown_failures = sum(1 for record in records if record["markdown_status"] == "failed")
    html_successes = sum(1 for record in records if str(record["html_status"]).startswith("success"))
    html_failures = sum(1 for record in records if record["html_status"] == "failed")
    warning_files = sum(1 for record in records if int(record["warning_count"]) > 0)
    schema_report_files = sum(1 for record in records if record["schema_report_paths"])

    md_path = reports_dir / "summary.md"
    lines = [
        "# Batch Validation Summary",
        "",
        f"- Total files discovered: {len(records)}",
        f"- Total files attempted: {len(records)}",
        f"- Markdown successes: {markdown_successes}",
        f"- Markdown failures: {markdown_failures}",
        f"- HTML successes: {html_successes}",
        f"- HTML failures: {html_failures}",
        f"- Files with schema warnings: {warning_files}",
        f"- Files with schema exception reports: {schema_report_files}",
        "",
        "## Top Warning Codes",
        "",
    ]
    if warning_counter:
        lines.extend(f"- `{code}`: {count}" for code, count in warning_counter.most_common(10))
    else:
        lines.append("- None")
    lines.extend(["", "## Top Failure Types", ""])
    if failure_counter:
        lines.extend(f"- `{failure}`: {count}" for failure, count in failure_counter.most_common(10))
    else:
        lines.append("- None")
    lines.extend(["", "## Partial Or Failed Files", ""])
    partial_or_failed = [
        record for record in records
        if "failed" in {record["markdown_status"], record["html_status"]} or int(record["warning_count"]) > 0
    ]
    if partial_or_failed:
        for record in partial_or_failed:
            lines.append(f"- `{record['source_path']}`")
            lines.append(
                f"  markdown={record['markdown_status']}, html={record['html_status']}, "
                f"warnings={record['warning_count']}, reports={record['schema_report_paths'] or 'none'}"
            )
            if record["failure_type"]:
                lines.append(f"  failure={record['failure_type']}: {record['failure_message']}")
    else:
        lines.append("- None")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return md_path, csv_path


def run_batch_validation(
    *,
    batch_dir: str,
    output_root: str | None,
    css_file: str | None,
    verbose: bool,
    log_file: str | None,
    formats: str,
    schema_warning_detail: str,
    media_index: bool,
    gh_file_schema_issue: bool,
    gh_repo: str,
) -> tuple[Path, Path, Path]:
    source_dir = Path(batch_dir).expanduser()
    if not source_dir.exists() or not source_dir.is_dir():
        raise RuntimeError(f"Batch source directory not found: {source_dir}")

    run_root = _ensure_safe_batch_output(source_dir, Path(output_root) if output_root else _default_batch_output_root())
    markdown_dir = run_root / "markdown"
    html_dir = run_root / "html"
    reports_dir = run_root / "reports"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_files = _discover_json_files(source_dir)
    logger.info("Discovered %d JSON files in %s", len(json_files), source_dir)

    include_markdown = formats in {"both", "markdown"}
    include_html = formats in {"both", "html"}
    records: list[dict[str, Any]] = []

    for json_file in json_files:
        logger.info("Batch processing %s", json_file.name)
        md_result = None
        html_result = None

        if include_markdown:
            md_result = export_file(
                input_file=str(json_file),
                format_name="markdown",
                output=str(markdown_dir),
                css_file=None,
                verbose=verbose,
                force=True,
                log_file=log_file,
                schema_warning_detail=schema_warning_detail,
                media_index=media_index,
                gh_file_schema_issue=gh_file_schema_issue,
                gh_repo=gh_repo,
            )
        if include_html:
            html_result = export_file(
                input_file=str(json_file),
                format_name="html",
                output=str(html_dir),
                css_file=css_file,
                verbose=verbose,
                force=True,
                log_file=log_file,
                schema_warning_detail=schema_warning_detail,
                media_index=media_index,
                gh_file_schema_issue=gh_file_schema_issue,
                gh_repo=gh_repo,
            )

        warning_codes = sorted(
            set((md_result.warning_codes or []) + (html_result.warning_codes or [] if html_result else []))
        )
        schema_paths = [
            str(result.schema_report_path)
            for result in (md_result, html_result)
            if result and result.schema_report_path
        ]
        failure_result = next(
            (result for result in (md_result, html_result) if result and result.status == "failed"),
            None,
        )
        records.append(
            {
                "source_path": str(json_file),
                "markdown_status": md_result.status if md_result else "skipped",
                "html_status": html_result.status if html_result else "skipped",
                "warning_count": max((md_result.warning_count if md_result else 0), (html_result.warning_count if html_result else 0)),
                "warning_codes": "|".join(warning_codes),
                "schema_report_paths": "|".join(schema_paths),
                "failure_type": failure_result.failure_type if failure_result else "",
                "failure_message": failure_result.failure_message if failure_result else "",
                "markdown_output": str(md_result.output_path) if md_result and md_result.output_path else "",
                "html_output": str(html_result.output_path) if html_result and html_result.output_path else "",
                "elapsed_seconds": round((md_result.elapsed_seconds if md_result else 0.0) + (html_result.elapsed_seconds if html_result else 0.0), 3),
            }
        )

    summary_path, csv_path = _write_batch_reports(records, reports_dir)
    logger.info("Batch validation complete. Run root: %s", run_root)
    logger.info("Summary report: %s", summary_path)
    logger.info("CSV report: %s", csv_path)
    return run_root, summary_path, csv_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Extract a ChatGPT conversation from JSON using chronological processing (v{__version__}).",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("input_file", nargs="?", help="Path to the input JSON file.")
    parser.add_argument("-o", "--output", help="Output path. For batch mode this is the run root directory.")
    parser.add_argument(
        "-f",
        "--format",
        choices=["markdown", "html", "jekyll"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument("-c", "--css-file", help="Path to a custom CSS file for HTML output.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug output.")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit.",
    )
    parser.add_argument("--log-file", help="Optional path to write logs to a file.")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing files.")
    parser.add_argument(
        "--schema-warning-detail",
        choices=["summary", "full"],
        default="summary",
        help="Show a schema drift summary only, or every warning entry (default: summary).",
    )
    parser.add_argument(
        "--media-index",
        action="store_true",
        help="Write a media inventory JSON file under a conversation-named subdirectory next to the output.",
    )
    parser.add_argument(
        "--gh-file-schema-issue",
        action="store_true",
        help="Use `gh` to file schema-drift issues automatically when warnings occur, with duplicate detection.",
    )
    parser.add_argument(
        "--gh-repo",
        default=_DEFAULT_GH_REPO,
        help=f"GitHub repository for automatic schema issue filing (default: {_DEFAULT_GH_REPO}).",
    )
    parser.add_argument("--jekyll-turn-id", help="Assistant turn ID to export when using --format jekyll.")
    parser.add_argument("--jekyll-base-slug", help="Base slug used for generated filenames when using --format jekyll.")
    parser.add_argument(
        "--jekyll-layout",
        default="page",
        help="Layout value to include in generated front matter for Jekyll output (default: page)",
    )
    parser.add_argument(
        "--jekyll-reference-title",
        default="References",
        help="Title to use for the references page when exporting to Jekyll.",
    )
    parser.add_argument(
        "--batch-dir",
        help="Directory of JSON files to batch-process into markdown/html validation outputs.",
    )
    parser.add_argument(
        "--batch-formats",
        choices=["both", "markdown", "html"],
        default="both",
        help="Formats to generate in batch mode (default: both).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.batch_dir:
        try:
            run_batch_validation(
                batch_dir=args.batch_dir,
                output_root=args.output,
                css_file=args.css_file,
                verbose=args.verbose,
                log_file=args.log_file,
                formats=args.batch_formats,
                schema_warning_detail=args.schema_warning_detail,
                media_index=args.media_index,
                gh_file_schema_issue=args.gh_file_schema_issue,
                gh_repo=args.gh_repo,
            )
            return
        except Exception as exc:
            logger.error("Batch validation failed: %s", exc)
            sys.exit(1)

    if not args.input_file:
        parser.error("input_file is required unless --batch-dir is provided")

    if not os.path.exists(args.input_file):
        logger.error("Input file not found: %s", args.input_file)
        sys.exit(1)

    result = export_file(
        input_file=args.input_file,
        format_name=args.format,
        output=args.output,
        css_file=args.css_file,
            verbose=args.verbose,
            force=args.force,
            log_file=args.log_file,
            schema_warning_detail=args.schema_warning_detail,
            media_index=args.media_index,
            gh_file_schema_issue=args.gh_file_schema_issue,
            gh_repo=args.gh_repo,
            jekyll_turn_id=args.jekyll_turn_id,
        jekyll_base_slug=args.jekyll_base_slug,
        jekyll_layout=args.jekyll_layout,
        jekyll_reference_title=args.jekyll_reference_title,
    )
    if result.status == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
