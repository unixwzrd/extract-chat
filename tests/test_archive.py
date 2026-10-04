from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from extract_chat.archive import ArchiveError, extract_archive


def test_extract_archive_finds_root_json(tmp_path: Path) -> None:
    source = tmp_path / "chat.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("chat.json", "{}")
        archive.writestr("chat/artifacts/generated/chart.png", b"png")
    extracted = extract_archive(source, tmp_path / "out")
    assert extracted.json_path.name == "chat.json"
    assert (extracted.root / "chat/artifacts/generated/chart.png").read_bytes() == b"png"


def test_extract_archive_rejects_traversal(tmp_path: Path) -> None:
    source = tmp_path / "bad.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("../escape.json", "{}")
    with pytest.raises(ArchiveError, match="Unsafe"):
        extract_archive(source, tmp_path / "out")


class UnflaggedUTF8Info(zipfile.ZipInfo):
    def _encodeFilenameFlags(self) -> tuple[bytes, int]:
        return self.filename.encode("utf-8"), self.flag_bits & ~0x800


@pytest.mark.parametrize("filename", ["readme_·_project.pdf", "where_it’s_needed.pdf"])
def test_extract_archive_recovers_manifest_confirmed_utf8_name(tmp_path: Path, filename: str) -> None:
    source = tmp_path / "chat.zip"
    path = f"chat/artifacts/uploaded/{filename}"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("chat.json", "{}")
        archive.writestr("chat/artifact-manifest.json", json.dumps({"artifacts": [{"relative_path": path}]}))
        archive.writestr(UnflaggedUTF8Info(path), b"artifact")
    with zipfile.ZipFile(source) as archive:
        assert path not in archive.namelist()
    extracted = extract_archive(source, tmp_path / "out")
    assert (extracted.root / path).read_bytes() == b"artifact"


def test_extract_archive_does_not_guess_unlisted_utf8_names(tmp_path: Path) -> None:
    source = tmp_path / "chat.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("chat.json", "{}")
        archive.writestr(UnflaggedUTF8Info("chat/café.txt"), b"artifact")
    extracted = extract_archive(source, tmp_path / "out")
    assert (extracted.root / "chat/caf├⌐.txt").read_bytes() == b"artifact"


def test_extract_archive_rejects_corrected_name_collision(tmp_path: Path) -> None:
    source = tmp_path / "chat.zip"
    path = "chat/artifacts/café.txt"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("chat.json", "{}")
        archive.writestr("chat/artifact-manifest.json", json.dumps({"artifacts": [{"relative_path": path}]}))
        archive.writestr(path, b"first")
        archive.writestr(UnflaggedUTF8Info(path), b"second")
    with pytest.raises(ArchiveError, match="Duplicate ZIP destination"):
        extract_archive(source, tmp_path / "out")


def test_extract_archive_preserves_case_distinct_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "chat.zip"
    paths = ["chat/artifacts/generated/report.xlsx", "chat/artifacts/generated/REPORT.xlsx"]
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("chat.json", "{}")
        archive.writestr("chat/artifact-manifest.json", json.dumps({"artifacts": [{"relative_path": p} for p in paths]}))
        archive.writestr(paths[0], b"first")
        archive.writestr(paths[1], b"second")
    extracted = extract_archive(source, tmp_path / "out")
    manifest = json.loads((extracted.root / "chat/artifact-manifest.json").read_text())
    first, second = manifest["artifacts"]
    assert (extracted.root / first["relative_path"]).read_bytes() == b"first"
    assert (extracted.root / second["relative_path"]).read_bytes() == b"second"
    assert second["relative_path"] == "chat/artifacts/generated/REPORT--2.xlsx"
    assert second["archive_relative_path"] == paths[1]
