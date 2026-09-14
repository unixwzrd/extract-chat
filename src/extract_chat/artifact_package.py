"""Read and place artifacts captured by LogGPT Plus archives."""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from extract_chat.schemas.render_models import RenderDocument

logger = logging.getLogger(__name__)

_FILE_SERVICE_PREFIX = "file-service://"
_SEDIMENT_PREFIX = "sediment://"
_SANDBOX_LOCATOR_RE = re.compile(r"sandbox:/(?:mnt/data|workspace/scratch)/[^\s)>\]\"']+")
_TABLE_EXTENSIONS = {".csv", ".tsv"}
_MAX_RENDERED_TABLE_BYTES = 1024 * 1024
_MAX_RENDERED_TABLE_ROWS = 200
_MAX_RENDERED_TABLE_COLUMNS = 50


def normalize_artifact_identifier(value: Any) -> str | None:
    """Return a stable ChatGPT file identifier when one is present."""

    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            normalized = normalize_artifact_identifier(item)
            if normalized:
                return normalized
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.startswith(_FILE_SERVICE_PREFIX):
        return text[len(_FILE_SERVICE_PREFIX) :]
    if text.startswith(_SEDIMENT_PREFIX):
        return text[len(_SEDIMENT_PREFIX) :]
    if text.startswith(("http://", "https://")):
        query_id = parse_qs(urlparse(text).query).get("id", [None])[0]
        return str(query_id) if query_id else None
    if text.startswith(("file-", "file_")):
        return text
    return None


def _media_identifiers(media_item: Any) -> list[str]:
    candidates: list[str] = []
    metadata = getattr(media_item, "metadata", {}) or {}
    for value in (
        getattr(media_item, "label", None),
        getattr(media_item, "url", None),
        metadata.get("value"),
        metadata.get("canonical_id"),
        metadata.get("asset_pointer"),
        metadata.get("file_id"),
    ):
        normalized = normalize_artifact_identifier(value)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _safe_artifact_path(package_root: Path, relative_path: str) -> Path | None:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        logger.warning("Ignoring unsafe artifact path in manifest: %s", relative_path)
        return None
    candidate = package_root.parent / relative if relative.parts and relative.parts[0] == package_root.name else package_root / relative
    try:
        resolved = candidate.resolve()
        allowed_root = package_root.parent.resolve()
        resolved.relative_to(allowed_root)
    except (OSError, ValueError):
        logger.warning("Ignoring unsafe artifact path in manifest: %s", relative_path)
        return None
    return resolved


def _sandbox_path_from_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    sandbox_path = parse_qs(urlparse(text).query).get("sandbox_path", [None])[0]
    if not sandbox_path:
        return None
    path = Path(str(sandbox_path))
    if not path.is_absolute() or ".." in path.parts:
        return None
    if not (str(path).startswith("/mnt/data/") or str(path).startswith("/workspace/scratch/")):
        return None
    return str(path)


def load_artifact_entries(input_path: Path) -> dict[str, dict[str, Any]]:
    """Load v2, v1, or legacy media entries associated with a conversation."""

    package_root = input_path.parent / input_path.stem
    manifest_paths = [
        package_root / "artifact-manifest.json",
        package_root / "media-manifest.json",
        package_root / "media" / "media-manifest.json",
    ]
    entries: dict[str, dict[str, Any]] = {}
    filename_entries: dict[str, dict[str, Any] | None] = {}

    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("Ignoring unreadable artifact manifest: %s", manifest_path)
            continue

        items = (payload.get("artifacts") or payload.get("items") or []) if isinstance(payload, dict) else []
        for item in items:
            if not isinstance(item, dict) or item.get("download_status", "downloaded") != "downloaded":
                continue
            relative_path = item.get("relative_path") or item.get("saved_path")
            if not relative_path and (item.get("saved_filename") or item.get("filename")):
                relative_path = f"media/{item.get('saved_filename') or item.get('filename')}"
            if not relative_path:
                continue
            artifact_path = _safe_artifact_path(package_root, str(relative_path))
            if artifact_path is None or not artifact_path.is_file():
                continue
            identifiers = {
                normalize_artifact_identifier(item.get(field))
                for field in ("canonical_id", "file_id", "asset_pointer", "source_url", "original_url")
            }
            canonical_identifier = next((value for value in identifiers if value is not None), None)
            entry = {
                "canonical_id": canonical_identifier,
                "absolute_path": artifact_path,
                "relative_path": str(relative_path),
                "display_name": item.get("original_filename") or item.get("saved_filename") or artifact_path.name,
                "original_url": item.get("source_url") or item.get("original_url"),
                "mime_type": item.get("detected_mime_type") or item.get("mime_type") or item.get("declared_mime_type"),
                "origin": item.get("origin"),
            }
            for identifier in identifiers - {None}:
                entries[str(identifier)] = {**entry, "canonical_id": identifier}
            sandbox_path = _sandbox_path_from_url(item.get("source_url") or item.get("original_url"))
            if sandbox_path:
                entries[f"sandbox:{sandbox_path}"] = entry
            original_filename = item.get("original_filename")
            if original_filename:
                filename = str(original_filename)
                existing = filename_entries.get(filename)
                filename_entries[filename] = entry if existing is None and filename not in filename_entries else None

    for filename, entry in filename_entries.items():
        if entry is not None:
            entries[f"filename:{filename}"] = entry

    for artifact_dir in (package_root / "artifacts", package_root / "media"):
        if not artifact_dir.exists():
            continue
        for artifact_path in artifact_dir.rglob("*"):
            if not artifact_path.is_file() or artifact_path.name.endswith("manifest.json"):
                continue
            identifier = normalize_artifact_identifier(artifact_path.stem) or artifact_path.stem
            entries.setdefault(
                identifier,
                {
                    "canonical_id": identifier,
                    "absolute_path": artifact_path,
                    "relative_path": str(artifact_path.relative_to(package_root)),
                    "display_name": artifact_path.name,
                    "original_url": None,
                    "mime_type": None,
                    "origin": artifact_path.parent.name if artifact_path.parent.name in {"generated", "uploaded", "derived"} else None,
                },
            )
    return entries


def _read_small_table(path: Path) -> list[list[str]] | None:
    if path.suffix.lower() not in _TABLE_EXTENSIONS or path.stat().st_size > _MAX_RENDERED_TABLE_BYTES:
        return None
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = []
            for index, row in enumerate(csv.reader(handle, delimiter=delimiter)):
                if index >= _MAX_RENDERED_TABLE_ROWS or len(row) > _MAX_RENDERED_TABLE_COLUMNS:
                    return None
                rows.append(row)
            return rows or None
    except (OSError, UnicodeError, csv.Error):
        return None


def attach_local_artifacts(*, document: RenderDocument, input_path: Path, output_path: Path | None) -> None:
    """Replace matching remote media pointers with safe local artifact links."""

    manifest_entries = load_artifact_entries(input_path)
    if not manifest_entries:
        return

    output_parent = output_path.parent if output_path is not None else input_path.parent

    def materialize(match: dict[str, Any]) -> tuple[Path, str]:
        artifact_path = Path(match["absolute_path"])
        if output_path is not None and output_path.stem != input_path.stem and artifact_path.parent != output_parent:
            category = match.get("origin") or "derived"
            if category not in {"generated", "uploaded", "derived"}:
                category = "derived"
            destination = output_parent / output_path.stem / "artifacts" / category / artifact_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if artifact_path.resolve() != destination.resolve():
                shutil.copy2(artifact_path, destination)
            artifact_path = destination
        return artifact_path, os.path.relpath(artifact_path, output_parent)

    for turn in document.turns:
        for item in turn.media_items:
            for identifier in _media_identifiers(item):
                match = manifest_entries.get(identifier)
                if not match:
                    continue
                artifact_path, relative_link = materialize(match)
                if item.url:
                    item.metadata["original_url"] = item.url
                item.metadata.update(
                    {
                        "canonical_id": match["canonical_id"],
                        "local_path": relative_link,
                        "display_name": match["display_name"],
                        "mime_type": match.get("mime_type"),
                        "origin": match.get("origin"),
                    }
                )
                table_rows = _read_small_table(artifact_path)
                if table_rows:
                    item.metadata["table_rows"] = table_rows
                item.url = relative_link
                item.label = str(match["display_name"])
                break

        def replace_sandbox_locator(match: re.Match[str]) -> str:
            locator = match.group(0)
            artifact = manifest_entries.get(locator)
            if artifact is None:
                filename = unquote(Path(urlparse(locator).path).name)
                artifact = manifest_entries.get(f"filename:{filename}")
            if artifact is None:
                return locator
            _, relative_link = materialize(artifact)
            return relative_link

        turn.content = _SANDBOX_LOCATOR_RE.sub(replace_sandbox_locator, turn.content)


def copy_artifact_package(input_path: Path, destination: Path, *, force: bool) -> list[Path]:
    """Copy a captured artifact package beside rendered output."""

    source_root = input_path.parent / input_path.stem
    if not source_root.exists() or source_root.resolve() == destination.resolve():
        return []
    copied: list[Path] = []
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        target = destination / source.relative_to(source_root)
        if target.exists() and not force:
            raise RuntimeError(f"Refusing to overwrite existing artifact: {target} (use --force)")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied
