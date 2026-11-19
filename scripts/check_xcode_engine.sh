#!/bin/bash
# Xcode embeds a prebuilt, audited runtime; builds never download dependencies.
set -euo pipefail

helper="${SCRIPT_INPUT_FILE_0:?Xcode must declare the helper bundle as an input}"
fail() { echo "error: $*" >&2; exit 1; }
[[ -x "$helper/Contents/MacOS/extract-chat" ]] || fail "Bundled engine is missing. Run scripts/build_macos_helper.sh in the qualified build environment first."
[[ -s "$helper/Contents/Resources/default.css" ]] || fail "Default stylesheet is missing. Rebuild the bundled helper."
if [[ "${CODE_SIGNING_ALLOWED:-YES}" != NO && "${EXPANDED_CODE_SIGN_IDENTITY:-}" == - ]]; then
    fail "Xcode selected Sign to Run Locally. Select your Apple Development team and enable automatic signing in Signing & Capabilities; the prepared engine uses certificate signing."
fi
if [[ -n "${MARKETING_VERSION:-}" ]]; then
    helper_version=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$helper/Contents/Info.plist")
    [[ "$helper_version" == "$MARKETING_VERSION" ]] || fail "Engine version $helper_version differs from app version $MARKETING_VERSION. Rebuild the bundled helper."
fi
/usr/bin/codesign --verify --deep --strict "$helper" || fail "Engine signature is invalid. Rebuild the bundled helper."
entitlements=$(/usr/bin/codesign -d --entitlements :- "$helper" 2>/dev/null)
for key in com.apple.security.app-sandbox com.apple.security.inherit; do
    key_path=${key//./\\.}
    [[ $(printf '%s' "$entitlements" | /usr/bin/plutil -extract "$key_path" raw -o - -) == true ]] || fail "Engine must have sandbox inheritance, not terminal entitlements."
done
# Reject debug/task-allow and any other entitlements on the inherited helper.
key_count=$(printf '%s' "$entitlements" | /usr/bin/plutil -p - | /usr/bin/awk '/=>/ {n++} END {print n+0}')
[[ "$key_count" == 2 ]] || fail "Inherited helper must have exactly the two sandbox entitlements."
for notice in THIRD-PARTY-NOTICES.txt NATIVE-RUNTIME-NOTICES.txt; do
    [[ -s "$helper/Contents/Resources/$notice" ]] || fail "Engine is missing required notices: $notice"
done
for encoding_cache in "$helper"/Contents/Resources/tokenizer-cache/*; do
    [[ -s "$encoding_cache" ]] || fail "Offline tokenizer cache is missing."
done

# An arm64-only engine must not silently enter a universal/Intel archive. Check
# every native component, not just the PyInstaller bootloader.
while IFS= read -r -d '' native; do
    if /usr/bin/file -b "$native" | /usr/bin/grep -q 'Mach-O'; then
        for architecture in ${ARCHS:?Xcode must specify target architectures}; do
            /usr/bin/lipo "$native" -verify_arch "$architecture" >/dev/null 2>&1 || fail "Engine component lacks $architecture: $native. Build a matching runtime before archiving."
        done
        # Copy-signing the outer app doesn't re-sign its native dependencies.
        # Require the prebuilt runtime to use the destination identity already.
        if [[ "${CODE_SIGNING_ALLOWED:-YES}" != NO && -n "${EXPANDED_CODE_SIGN_IDENTITY_NAME:-}" ]]; then
            authority=$(/usr/bin/codesign -d --verbose=2 "$native" 2>&1 | /usr/bin/sed -n 's/^Authority=//p' | /usr/bin/head -1)
            [[ "$authority" == "$EXPANDED_CODE_SIGN_IDENTITY_NAME" ]] || fail "Engine signing identity differs from Xcode. Rebuild it with EXTRACT_CHAT_SIGN_IDENTITY set to the selected signing certificate."
        fi
    fi
done < <(/usr/bin/find "$helper/Contents" -type f -print0)
echo "Bundled engine signature, inherited sandbox, notices and target architectures verified."
