"""Safe readers for LogGPT+ conversation archives."""

from __future__ import annotations

import json
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class ArchiveError(RuntimeError):
    """Raised when an archive is unsafe or does not contain a conversation."""


@dataclass(frozen=True)
class ExtractedArchive:
    json_path: Path
    root: Path


def extract_archive(source: Path, destination: Path) -> ExtractedArchive:
    """Extract a ZIP without permitting traversal, absolute paths, or symlinks."""

    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        expected_paths = _manifest_paths(archive)
        extracted_paths: set[PurePosixPath] = set()
        portable_paths: set[str] = set()
        renamed_paths: dict[str, str] = {}
        for info in archive.infolist():
            member = PurePosixPath(_member_name(info, expected_paths))
            if member.is_absolute() or ".." in member.parts:
                raise ArchiveError(f"Unsafe ZIP member: {info.filename}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ArchiveError(f"ZIP symlinks are not supported: {info.filename}")
            if member in extracted_paths:
                raise ArchiveError(f"Duplicate ZIP destination: {member}")
            extracted_paths.add(member)
            original_member = member
            ordinal = 2
            while str(member).casefold() in portable_paths:
                if info.is_dir():
                    raise ArchiveError(f"Case-colliding ZIP directory: {member}")
                member = original_member.with_name(f"{original_member.stem}--{ordinal}{original_member.suffix}")
                ordinal += 1
            portable_paths.add(str(member).casefold())
            if member != original_member:
                renamed_paths[str(original_member)] = str(member)
            target = destination.joinpath(*member.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    if renamed_paths:
        for manifest_path in destination.rglob("artifact-manifest.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for artifact in manifest.get("artifacts", []):
                old_path = artifact.get("relative_path")
                if old_path in renamed_paths:
                    artifact.setdefault("archive_relative_path", old_path)
                    artifact["relative_path"] = renamed_paths[old_path]
                    artifact["saved_filename"] = PurePosixPath(renamed_paths[old_path]).name
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    json_files = sorted(path for path in destination.rglob("*.json") if path.name not in {"artifact-manifest.json", "media-manifest.json"})
    root_json = [path for path in json_files if path.parent == destination]
    candidates = root_json or json_files
    if len(candidates) != 1:
        raise ArchiveError(f"Expected one conversation JSON in {source}; found {len(candidates)}")
    return ExtractedArchive(json_path=candidates[0], root=destination)


def _manifest_paths(archive: zipfile.ZipFile) -> set[str]:
    paths: set[str] = set()
    for info in archive.infolist():
        if PurePosixPath(info.filename).name != "artifact-manifest.json":
            continue
        manifest = json.loads(archive.read(info))
        if not isinstance(manifest, dict):
            continue
        for artifact in manifest.get("artifacts", []):
            if isinstance(artifact, dict) and isinstance(artifact.get("relative_path"), str):
                paths.add(artifact["relative_path"])
    return paths


def _member_name(info: zipfile.ZipInfo, expected_paths: set[str]) -> str:
    # Older LogGPT ZIPs can contain UTF-8 names without the ZIP UTF-8 flag.
    # Correct only names confirmed by the manifest; preserve genuine CP437 names.
    if info.flag_bits & 0x800 or info.filename in expected_paths:
        return info.filename
    try:
        utf8_name = info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename
    return utf8_name if utf8_name in expected_paths else info.filename
