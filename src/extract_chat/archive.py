"""Safe readers for LogGPT+ conversation archives."""

from __future__ import annotations

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
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise ArchiveError(f"Unsafe ZIP member: {info.filename}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ArchiveError(f"ZIP symlinks are not supported: {info.filename}")
            target = destination.joinpath(*member.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    json_files = sorted(path for path in destination.rglob("*.json") if path.name not in {"artifact-manifest.json", "media-manifest.json"})
    root_json = [path for path in json_files if path.parent == destination]
    candidates = root_json or json_files
    if len(candidates) != 1:
        raise ArchiveError(f"Expected one conversation JSON in {source}; found {len(candidates)}")
    return ExtractedArchive(json_path=candidates[0], root=destination)
