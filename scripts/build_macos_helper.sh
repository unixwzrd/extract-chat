#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
output_dir="$repo_dir/macos/ExtractChatApp/BundledHelper"
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

if ! python -c 'import PyInstaller' 2>/dev/null; then
  echo "PyInstaller is required. Install the mac-app extra in a build environment:" >&2
  echo "  python -m pip install -e '.[mac-app]'" >&2
  exit 2
fi

python -m PyInstaller \
  --clean \
  --noconfirm \
  --onefile \
  --name extract-chat \
  --distpath "$output_dir" \
  --workpath "$work_dir/build" \
  --specpath "$work_dir" \
  "$repo_dir/src/extract_chat/cli.py"

codesign --display --verbose=2 "$output_dir/extract-chat" >/dev/null 2>&1 || true
echo "Built $output_dir/extract-chat"
echo "Add this executable to the ExtractChatApp target Copy Bundle Resources phase before archiving."
