#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
output_dir="$repo_dir/build/macos-qualification/helper"
app_name=ExtractChatEngine.app
entitlements="$repo_dir/macos/Helper.entitlements"
[[ $# -eq 0 ]] || { echo "Usage: $0 (the app provides CLI mode; no separate companion)" >&2; exit 2; }
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

if ! python -c 'import PyInstaller' 2>/dev/null; then
  echo "PyInstaller is required. Install the mac-app extra in a build environment:" >&2
  echo "  python -m pip install -e '.[mac-app]'" >&2
  exit 2
fi

python -c 'from importlib.metadata import version; assert version("tree-sitter-language-pack") == "0.9.1", "Install with -c macos/constraints.txt for the qualified macOS 13 candidate"'
python "$repo_dir/scripts/audit_macos_dependencies.py" --output "$repo_dir/build/macos-qualification/audit-compatible" --minimum-macos 13.0
export TIKTOKEN_CACHE_DIR="$repo_dir/build/macos-qualification/tokenizer-cache"
python -c 'import tiktoken; [tiktoken.get_encoding(name) for name in ("o200k_base", "cl100k_base")]'

export EXTRACT_CHAT_SOURCE_ROOT="$repo_dir"
cp "$repo_dir/macos/engine.spec.in" "$work_dir/engine.spec"
python -c 'import sys; from pathlib import Path; from extract_chat.css_manager import get_default_css_content; Path(sys.argv[1]).write_text(get_default_css_content(), encoding="utf-8")' "$work_dir/default.css"
python -m PyInstaller \
  --clean \
  --noconfirm \
  --distpath "$output_dir" \
  --workpath "$work_dir/build" \
  "$work_dir/engine.spec"

audit_dir="$repo_dir/build/macos-qualification/audit-frozen"
python "$repo_dir/scripts/audit_frozen_macos.py" "$output_dir/$app_name" --output "$audit_dir"
cp "$audit_dir/NATIVE-RUNTIME-NOTICES.txt" "$output_dir/$app_name/Contents/Resources/"
if [[ -n "${EXTRACT_CHAT_SIGN_IDENTITY:-}" ]]; then
  codesign --force --options runtime --sign "$EXTRACT_CHAT_SIGN_IDENTITY" --entitlements "$entitlements" "$output_dir/$app_name"
  codesign --verify --deep --strict "$output_dir/$app_name"
fi
echo "Built candidate: $output_dir/$app_name"
echo "Embed the complete nested app under Contents/Helpers, not Copy Bundle Resources."
echo "Sandboxed app execution and the frozen native-library audit remain separate qualification gates."
