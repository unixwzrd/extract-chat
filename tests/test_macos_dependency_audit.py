"""Deployment checks must not mistake dylib version numbers for macOS versions."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("macos_audit", Path(__file__).parents[1] / "scripts" / "audit_macos_dependencies.py")
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize(("commands", "expected"), [
    ("Load command 0\n cmd LC_LOAD_DYLIB\n current version 1356.0.0\nLoad command 1\n cmd LC_BUILD_VERSION\n platform 1\n minos 11.0\n sdk 26.5\n", "11.0"),
    ("Load command 0\n cmd LC_VERSION_MIN_MACOSX\n version 10.13\n sdk 15.0\n", "10.13"),
    ("Load command 0\n cmd LC_BUILD_VERSION\n platform 1\n minos 15.0\n sdk 26.5\n", "15.0"),
    ("Load command 0\n cmd LC_LOAD_DYLIB\n current version 1356.0.0\n", None),
])
def test_parse_native_minimum(commands: str, expected: str | None) -> None:
    assert audit.parse_native_minimum(commands) == expected
