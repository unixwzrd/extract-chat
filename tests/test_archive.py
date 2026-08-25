from __future__ import annotations

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
