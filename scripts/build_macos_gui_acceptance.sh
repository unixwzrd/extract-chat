#!/bin/bash
set -euo pipefail
repo_dir=$(cd "$(dirname "$0")/.." && pwd)
destination_app="$repo_dir/build/macos-qualification/Extract Chat GUI Acceptance.app"
# Never overlay signed code bundles: removed resources would survive ditto and
# invalidate the helper's resource seal. Publish only a freshly verified app.
staging_dir=$(mktemp -d "$repo_dir/build/macos-qualification/acceptance-build.XXXXXX")
app="$staging_dir/Extract Chat GUI Acceptance.app"
sources="$repo_dir/macos/ExtractChatApp/Sources/ExtractChatApp"
: "${EXTRACT_CHAT_SIGN_IDENTITY:?Choose a local development signing identity}"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Helpers" "$app/Contents/Resources"
cp "$repo_dir/macos/Tests/GUIAcceptance-Info.plist" "$app/Contents/Info.plist"
xcrun actool "$repo_dir/macos/ExtractChatApp/Assets.xcassets" --compile "$app/Contents/Resources" --platform macosx --minimum-deployment-target 14.0 --app-icon AppIcon --output-partial-info-plist "$repo_dir/build/macos-qualification/acceptance-icon-info.plist"
test -f "$app/Contents/Resources/AppIcon.icns"
ditto "$repo_dir/build/macos-qualification/helper/ExtractChatEngine.app" "$app/Contents/Helpers/ExtractChatEngine.app"
xcrun swiftc -parse-as-library -target arm64-apple-macos14.0 "$sources/ConversionRunner.swift" "$sources/ConversionPermissions.swift" "$sources/CLIInstaller.swift" "$sources/CLIRunner.swift" "$sources/ExportModel.swift" "$sources/ExportView.swift" "$repo_dir/macos/Tests/GUIAcceptance.swift" -o "$app/Contents/MacOS/Acceptance"
codesign --force --options runtime --sign "$EXTRACT_CHAT_SIGN_IDENTITY" --entitlements "$repo_dir/macos/ExtractChatApp/ExtractChatApp.entitlements" "$app"
codesign --verify --deep --strict "$app"
if [[ -d "$destination_app" ]]; then
    mv "$destination_app" "$staging_dir/previous.app"
fi
mv "$app" "$destination_app"
echo "Built sandboxed product-view acceptance host: $destination_app"
