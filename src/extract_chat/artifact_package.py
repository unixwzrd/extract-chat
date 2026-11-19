"""Read and place artifacts captured by LogGPT Plus archives."""

from __future__ import annotations

import csv
import filecmp
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from extract_chat.schemas.render_models import MediaItem, RenderDocument
from extract_chat.formatters.display_links import rewrite_artifact_links

logger = logging.getLogger(__name__)

_FILE_SERVICE_PREFIX = "file-service://"
_SEDIMENT_PREFIX = "sediment://"
_TABLE_EXTENSIONS = {".csv", ".tsv"}
_MAX_RENDERED_TABLE_BYTES = 1024 * 1024
_MAX_RENDERED_TABLE_ROWS = 200
_MAX_RENDERED_TABLE_COLUMNS = 50
_PACKAGE_MANIFESTS = ("artifact-manifest.json", "media-manifest.json")


def artifact_package_root(input_path: Path) -> Path | None:
    """Prefer artifacts beside the JSON; also read legacy named packages."""
    for root in (input_path.parent, input_path.parent / input_path.stem):
        if any((root / name).is_file() for name in _PACKAGE_MANIFESTS) or any((root / name).is_dir() for name in ("artifacts", "media")):
            if root.is_symlink():
                raise ValueError(f"Symlinked artifact package is not supported: {root}")
            return root
    return None


@dataclass(frozen=True)
class ArtifactCopyResult:
    artifact_copied: tuple[Path, ...] = ()
    artifact_reused: tuple[Path, ...] = ()
    metadata_copied: tuple[Path, ...] = ()
    metadata_reused: tuple[Path, ...] = ()

    @property
    def artifact_total(self) -> int:
        return len(self.artifact_copied) + len(self.artifact_reused)

    @property
    def metadata_total(self) -> int:
        return len(self.metadata_copied) + len(self.metadata_reused)


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
    if text.startswith(("file-", "file_", "CalpicoFile_")):
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
        allowed_root = package_root.resolve()
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


def load_artifact_entries(input_path: Path, *, unavailable: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Load v2, v1, or legacy media entries associated with a conversation."""

    package_root = artifact_package_root(input_path)
    if package_root is None:
        return {}
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
            if not isinstance(item, dict):
                continue
            filename = str(item.get("original_filename") or item.get("saved_filename") or item.get("filename") or "")
            if item.get("download_status", "downloaded") != "downloaded":
                if unavailable is not None and filename:
                    unavailable[filename] = str(item.get("failure_reason") or "The artifact was not captured in the supplied package.")
                continue
            relative_path = item.get("relative_path") or item.get("saved_path")
            if not relative_path and (item.get("saved_filename") or item.get("filename")):
                relative_path = f"media/{item.get('saved_filename') or item.get('filename')}"
            if not relative_path:
                continue
            artifact_path = _safe_artifact_path(package_root, str(relative_path))
            if artifact_path is None or not artifact_path.is_file():
                if unavailable is not None and filename:
                    unavailable[filename] = "The manifest references a file absent from the supplied package."
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

    for artifact_dir in (package_root / "artifacts", package_root / "media"):
        if not artifact_dir.exists():
            continue
        for artifact_path in artifact_dir.rglob("*"):
            if not artifact_path.is_file() or artifact_path.is_symlink() or not artifact_path.resolve().is_relative_to(package_root.resolve()) or artifact_path.name.endswith("manifest.json"):
                continue
            identifier = normalize_artifact_identifier(artifact_path.stem) or artifact_path.stem
            entry = {
                "canonical_id": identifier,
                "absolute_path": artifact_path,
                "relative_path": str(artifact_path.relative_to(package_root)),
                "display_name": artifact_path.name,
                "original_url": None,
                "mime_type": None,
                "origin": artifact_path.parent.name if artifact_path.parent.name in {"generated", "uploaded", "derived"} else None,
            }
            entries.setdefault(identifier, entry)
            existing = filename_entries.get(artifact_path.name)
            if artifact_path.name not in filename_entries:
                filename_entries[artifact_path.name] = entry
            elif existing is not None and Path(existing["absolute_path"]).resolve() != artifact_path.resolve():
                filename_entries[artifact_path.name] = None
    for filename, entry in filename_entries.items():
        if entry is not None:
            entries[f"filename:{filename}"] = entry
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


def attach_local_artifacts(*, document: RenderDocument, input_path: Path, output_path: Path | None, artifact_destination: Path | None = None) -> None:
    """Replace matching remote media pointers with safe local artifact links."""

    unavailable: dict[str, str] = {}
    manifest_entries = load_artifact_entries(input_path, unavailable=unavailable)

    output_parent = output_path.parent if output_path is not None else input_path.parent

    def materialize(match: dict[str, Any]) -> tuple[Path, str]:
        artifact_path = Path(match["absolute_path"])
        if output_path is not None:
            source_root = artifact_package_root(input_path).resolve()
            relative = artifact_path.relative_to(source_root)
            destination = (artifact_destination if artifact_destination is not None else output_parent / output_path.stem) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if artifact_path.resolve() != destination.resolve():
                shutil.copy2(artifact_path, destination)
            artifact_path = destination
        return artifact_path, quote(os.path.relpath(artifact_path, output_parent), safe="/")

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

        missing: set[str] = set()
        def replace_sandbox_locator(locator: str, label: str) -> str | None:
            artifact = manifest_entries.get(locator)
            filename = unquote(Path(urlparse(locator).path).name)
            if artifact is None:
                artifact = manifest_entries.get(f"filename:{filename}")
            if artifact is None:
                reason = unavailable.get(filename) or "No unambiguous captured file matches this sandbox link in the supplied package."
                if locator not in missing:
                    turn.media_items.append(MediaItem(kind="unavailable_artifact", label=filename or label, turn_id=turn.turn_id, metadata={"unavailable_reason": reason, "source_locator": locator}))
                    missing.add(locator)
                    logger.warning("Artifact not captured: %s — %s", filename or label, reason)
                return None
            _, relative_link = materialize(artifact)
            return relative_link

        turn.content = rewrite_artifact_links(turn.content, replace_sandbox_locator)
        # Associate prompt provenance with the exact captured asset, not a
        # filename/title guess or another image in the same assistant turn.
        local_media = {str(item.metadata.get("canonical_id")): item for item in turn.media_items if item.metadata.get("local_path")}
        for activity in turn.tools_used:
            for image in activity.metadata.get("images") or []:
                match = local_media.get(normalize_artifact_identifier(image.get("asset_pointer")))
                if match:
                    image["local_path"] = match.metadata["local_path"]
                    image["display_name"] = match.metadata.get("display_name") or match.label


def _artifact_copy_plan(input_path: Path, destination: Path) -> list[tuple[Path, Path]]:
    source_root = artifact_package_root(input_path)
    if source_root is None or source_root.resolve() == destination.resolve():
        return []
    plan: list[tuple[Path, Path]] = []
    # Copy only captured artifacts and their manifests, not previous renders,
    # chunks, source JSON, inventories, or arbitrary sibling files on reruns.
    for name in (*_PACKAGE_MANIFESTS, "artifacts", "media"):
        entry = source_root / name
        for source in ([entry, *entry.rglob("*")] if entry.is_dir() else [entry]):
            if source.is_symlink():
                raise ValueError(f"Symlinked artifact is not supported: {source}")
            if source.is_file():
                plan.append((source, destination / source.relative_to(source_root)))
    return plan


def _same_file_content(source: Path, target: Path) -> bool:
    return target.is_file() and source.stat().st_size == target.stat().st_size and filecmp.cmp(source, target, shallow=False)


def validate_artifact_package_destination(input_path: Path, destination: Path, *, force: bool) -> None:
    """Refuse conflicting artifact targets before rendering any output."""

    if force:
        return
    for source, target in _artifact_copy_plan(input_path, destination):
        if target.exists() and not _same_file_content(source, target):
            raise RuntimeError(f"Refusing to overwrite existing artifact: {target} (use --force)")


def copy_artifact_package(input_path: Path, destination: Path, *, force: bool, root_relative: bool = False) -> ArtifactCopyResult:
    """Copy a captured artifact package beside rendered output."""

    plan = _artifact_copy_plan(input_path, destination)
    validate_artifact_package_destination(input_path, destination, force=force)
    artifact_copied: list[Path] = []
    artifact_reused: list[Path] = []
    metadata_copied: list[Path] = []
    metadata_reused: list[Path] = []
    for source, target in plan:
        relative = target.relative_to(destination)
        is_artifact = bool(relative.parts) and relative.parts[0] in {"artifacts", "media"} and target.name not in {
            "artifact-manifest.json",
            "media-manifest.json",
        }
        if target.exists() and _same_file_content(source, target):
            (artifact_reused if is_artifact else metadata_reused).append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        source_root = artifact_package_root(input_path)
        if relative == Path("artifact-manifest.json") and (root_relative or destination.name != source_root.name):
            manifest = json.loads(target.read_text(encoding="utf-8"))
            changed = False
            for artifact in manifest.get("artifacts", []):
                old_path = artifact.get("relative_path")
                if not isinstance(old_path, str):
                    continue
                old_relative = Path(old_path)
                if old_relative.parts and old_relative.parts[0] == source_root.name:
                    artifact.setdefault("archive_relative_path", old_path)
                    artifact["relative_path"] = str(Path(*old_relative.parts[1:]) if root_relative else Path(destination.name).joinpath(*old_relative.parts[1:]))
                    changed = True
            if changed:
                target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (artifact_copied if is_artifact else metadata_copied).append(target)
    return ArtifactCopyResult(
        artifact_copied=tuple(artifact_copied),
        artifact_reused=tuple(artifact_reused),
        metadata_copied=tuple(metadata_copied),
        metadata_reused=tuple(metadata_reused),
    )
