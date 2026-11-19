#!/usr/bin/env python3
"""Reconcile frozen native code with installed wheel/Conda notice evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from importlib.metadata import distribution
from pathlib import Path

from audit_macos_dependencies import dependency_closure, native_minimum


def audit(bundle: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    owners: dict[str, list[str]] = {}
    for name in dependency_closure(["extract-chat"], ("token-counting",)):
        for file in distribution(name).files or []:
            if str(file).endswith((".so", ".dylib")):
                owners.setdefault(file.name, []).append(name)
    conda: dict[str, dict] = {}
    for metadata in (Path(sys.base_prefix) / "conda-meta").glob("*.json"):
        record = json.loads(metadata.read_text(encoding="utf-8"))
        for file in record.get("files", []):
            if file.endswith((".so", ".dylib")):
                conda[Path(file).name] = record
    rows, blockers, notices = [], [], []
    seen: set[Path] = set()
    conda_seen: set[str] = set()
    for file in sorted(bundle.rglob("*")):
        if file.suffix not in {".so", ".dylib"} or not file.is_file() or file.resolve() in seen:
            continue
        seen.add(file.resolve())
        required = native_minimum(file)
        package_owners = owners.get(file.name, [])
        row = {"path": str(file.relative_to(bundle)), "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "minimum_macos": required, "wheel_owners": package_owners}
        if required and tuple(map(int, required.split("."))) > (13, 0):
            blockers.append(f"{file.name}: macOS {required}")
        record = conda.get(file.name)
        if not package_owners and record:
            name = record["name"]
            row["runtime_package"] = {"name": name, "version": record["version"], "license": record.get("license"), "source": record.get("url")}
            if name not in conda_seen:
                conda_seen.add(name)
                location = record.get("link", {}).get("source")
                license_root = Path(location) / "info" / "licenses" if location else None
                texts = sorted(license_root.rglob("*")) if license_root and license_root.is_dir() else []
                if not any(text.is_file() for text in texts):
                    blockers.append(f"Missing original native-runtime notices: {name}")
                for text in texts:
                    if text.is_file():
                        notices.append(f"\n{'=' * 72}\n{name} {record['version']}: {text.name}\n{'=' * 72}\n{text.read_text(encoding='utf-8', errors='replace')}")
        elif not package_owners:
            blockers.append(f"Unattributed native library: {file.name}")
        if "readline" in file.name:
            blockers.append(f"Unused GNU Readline must not be bundled: {file.name}")
        rows.append(row)
    result = {"status": "blocked" if blockers else "evidence-collected", "native_libraries": rows, "blockers": blockers,
              "limitations": ["This does not prove runtime behavior on macOS 13 or Intel", "Review wheel/native license alternatives and tokenizer asset redistribution before release"]}
    (output / "frozen-native-inventory.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output / "NATIVE-RUNTIME-NOTICES.txt").write_text("Native runtime candidate notices.\n" + "\n".join(notices), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.bundle, args.output)
    print(json.dumps({"status": result["status"], "libraries": len(result["native_libraries"]), "blockers": result["blockers"]}, indent=2))
    raise SystemExit(2 if result["blockers"] else 0)
