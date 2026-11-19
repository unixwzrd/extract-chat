#!/bin/bash
# Mechanical downsampling only; the original artwork stays untouched.
set -euo pipefail
repo_dir=$(cd "$(dirname "$0")/.." && pwd)
master="$repo_dir/macos/Artwork/ExtractChat-Icon.png"
destination="$repo_dir/macos/ExtractChatApp/Assets.xcassets/AppIcon.appiconset"
[[ -f "$master" && -f "$destination/Contents.json" ]] || { echo "Missing icon master or asset catalog." >&2; exit 1; }
for points in 16 32 128 256 512; do
    /usr/bin/sips -z "$points" "$points" "$master" --out "$destination/icon_${points}x${points}.png" >/dev/null
    pixels=$((points * 2))
    /usr/bin/sips -z "$pixels" "$pixels" "$master" --out "$destination/icon_${points}x${points}@2x.png" >/dev/null
done
echo "Generated all ten macOS AppIcon slots from $master"
