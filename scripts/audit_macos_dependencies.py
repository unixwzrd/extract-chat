#!/usr/bin/env python3
"""Record the resolved macOS candidate's dependency and notice evidence.

This is an inventory, not an automatic legal approval. Native dependencies of
the eventual frozen bundle must also be reconciled before distribution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def dependency_closure(roots: list[str], extras: tuple[str, ...] = ()) -> set[str]:
    pending = [(canonicalize_name(root), extras) for root in roots]
    visited: set[tuple[str, tuple[str, ...]]] = set()
    result: set[str] = set()
    while pending:
        name, selected = pending.pop()
        if (name, selected) in visited:
            continue
        visited.add((name, selected))
        result.add(name)
        for value in distribution(name).requires or []:
            requirement = Requirement(value)
            if requirement.marker and not any(requirement.marker.evaluate({"extra": extra}) for extra in ("", *selected)):
                continue
            pending.append((canonicalize_name(requirement.name), tuple(sorted(requirement.extras))))
    return result


def parse_native_minimum(output: str) -> str | None:
    versions = []
    for command in re.split(r"\nLoad command \d+\n", output):
        field = "minos" if "cmd LC_BUILD_VERSION\n" in command else "version" if "cmd LC_VERSION_MIN_MACOSX\n" in command else None
        if field:
            match = re.search(rf"^\s*{field}\s+(\d+\.\d+(?:\.\d+)?)\s*$", command, re.MULTILINE)
            if match:
                versions.append(match[1])
    return max(versions, key=lambda value: tuple(map(int, value.split(".")))) if versions else None


def native_minimum(path: Path) -> str | None:
    result = subprocess.run(["/usr/bin/otool", "-l", str(path)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Unable to inspect native library {path}: {result.stderr.strip()}")
    return parse_native_minimum(result.stdout)


def inventory(output: Path, minimum: str) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    runtime = dependency_closure(["extract-chat"], ("token-counting",))
    build = dependency_closure(["pyinstaller"])
    notices: list[str] = []
    records = []
    blockers = []
    for name in sorted(runtime | build):
        dist = distribution(name)
        license_files = []
        native_files = []
        for relative in dist.files or []:
            path = Path(dist.locate_file(relative))
            if not path.is_file():
                continue
            # Wheel metadata carries original license files, including bundled
            # native-library notices (notably Pillow's complete notice file).
            if ".dist-info/" in str(relative) and any(word in str(relative).lower() for word in ("license", "copying", "notice", "copyright")):
                data = path.read_bytes()
                license_files.append({"path": str(relative), "sha256": hashlib.sha256(data).hexdigest()})
                notices.append(f"\n{'=' * 72}\n{name} {dist.version}: {relative}\n{'=' * 72}\n{data.decode('utf-8', errors='replace')}")
            if name in runtime and path.suffix in {".so", ".dylib"}:
                required = native_minimum(path)
                native_files.append({"path": str(relative), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "minimum_macos": required})
                if required and tuple(map(int, required.split("."))) > tuple(map(int, minimum.split("."))):
                    blockers.append(f"{name} {dist.version}: {relative} requires macOS {required}, above target {minimum}")
        if not license_files:
            blockers.append(f"{name} {dist.version}: no packaged license/notice text found; source inspection required")
        direct = dist.read_text("direct_url.json")
        records.append({
            "name": name, "version": dist.version,
            "role": "runtime" if name in runtime else "build-only",
            "license_expression": dist.metadata.get("License-Expression"),
            "declared_license": dist.metadata.get("License"),
            "classifiers": [value for value in dist.metadata.get_all("Classifier", []) if value.startswith("License")],
            "project_urls": dist.metadata.get_all("Project-URL", []),
            "source": json.loads(direct) if direct else {"project": f"https://pypi.org/project/{name}/{dist.version}/"},
            "requirements": dist.requires or [], "notices": license_files, "native_files": native_files,
        })
    python_license = Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"
    if python_license.is_file():
        notices.insert(0, "Python runtime license and bundled component notices\n\n" + python_license.read_text(encoding="utf-8"))
    else:
        blockers.append("Python runtime license file missing; supply the runtime distribution's original notices")
    result = {
        "status": "blocked" if blockers else "requires-frozen-bundle-review",
        "python": platform.python_version(), "architecture": platform.machine(), "target_macos": minimum,
        "python_source": "https://github.com/python/cpython", "python_license_sha256": hashlib.sha256(python_license.read_bytes()).hexdigest() if python_license.exists() else None,
        "packages": records, "blockers": blockers,
        "remaining": ["Reconcile native libraries actually shipped by the frozen bundle", "Review license obligations and source/notice requirements", "Qualify sandboxed execution and security-scoped file access", "Qualify Intel separately"],
    }
    (output / "dependency-inventory.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output / "THIRD-PARTY-NOTICES.txt").write_text("Candidate notices: inclusion is not distribution approval.\n" + "\n".join(notices), encoding="utf-8")
    frozen = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True, text=True, check=True)
    (output / "resolved-requirements.txt").write_text(frozen.stdout, encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-macos", default="13.0")
    args = parser.parse_args()
    result = inventory(args.output, args.minimum_macos)
    print(json.dumps({"status": result["status"], "packages": len(result["packages"]), "blockers": result["blockers"]}, indent=2))
    if result["blockers"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
