# Extract Chat for macOS

Version 1.0.0 is an unreleased development candidate for macOS 14 or later. Local builds and acceptance tests pass on Apple Silicon; they do not establish App Store distribution readiness, Intel support, or behavior on every supported OS/cloud provider. See [App Store preparation](APP-STORE-PREPARATION.md) for the current release gates and [dependency qualification](DEPENDENCY-AUDIT.md) for the runtime audit.

## Build

Open `ExtractChatApp/ExtractChatApp.xcodeproj` and use the shared ExtractChatApp scheme with My Mac. Retain automatic signing, App Sandbox and Hardened Runtime. Prepare the frozen engine using the same certificate identity as Xcode, in the isolated packaging environment:

```sh
python -m pip install -c macos/constraints.txt '.[mac-app,token-counting]'
EXTRACT_CHAT_SIGN_IDENTITY='Apple Development: Your Name (CERTIFICATEID)' bash scripts/build_macos_helper.sh
```

Run those commands from the repository root. Rebuild the engine after Python/dependency changes; Xcode embeds the prepared runtime rather than downloading packages or using developer-installed Python. Its build phase checks signing, notices, tokenizer data and matching architectures before copying the complete `ExtractChatEngine.app` into Contents/Helpers. The engine has exactly the sandbox/inherit entitlements. It retains a macOS 13 compatibility baseline while the containing application requires macOS 14.

The current engine is arm64 only. A universal archive must fail until a qualified matching Intel engine exists; do not bypass the architecture/signature checks. SwiftPM provides a compilation check, not a signed application bundle:

```sh
swift build --package-path macos/ExtractChatApp
```

## Extraction workflow

Add conversation JSON, LGPT or legacy ZIP files through Add Files, File > Open, drag/drop, or Finder Open With. Source adapters recognize ChatGPT/Work, Dots and Hermes Desktop; the [main README](../README.md) describes source-specific boundaries. Commands and tool payloads are rendered as inert text, never executed.

Choose Markdown, HTML or Both and select OK. Each input produces its own managed result folder beside the source by default. Choose Folder sets a common parent; Clear restores Beside each input. Original inputs are unchanged. Completed results retain the exact source JSON under its original filename, available artifacts/manifests, requested transcripts, and optional inventory/continuity chunks. Reprocessing the retained JSON discovers adjacent artifacts rather than copying old renders or unrelated siblings.

Leave Overwrite off for numbered collisions. Overwrite replaces only recognized, intact managed results; unfinished staging is not published. Show Results reveals successful outputs. Failures open selectable diagnostics; Details reopens them. A failed item does not stop later inputs.

The footer offers Quit when idle/finished, Cancel for a pending or running operation, and disabled Cancelling during cleanup. Pending Cancel clears the queue and restores accepted settings without closing the app. Active Cancel interrupts the engine cooperatively, preserving earlier successes; blocked file-provider operations can delay cleanup. Close on successful completion defaults off and quits only after complete batch success.

## Options and rendering

- Reset to Defaults keeps the selected queue; OK persists accepted settings and Cancel restores them. Resetting conversion settings does not revoke permissions.
- Local display time is the default. The optional override accepts IANA zones, UTC or a fixed UTC offset; timestamps include their zone while source epochs and UTC-derived filenames remain unchanged.
- Conversation index optionally adds compact turn navigation. HTML links to external pages/files open separately while same-page citations and index anchors remain local.
- Tool JSON offers readable decoded strings plus raw JSON, formatted escaped JSON, or original escaped JSON. Thoughts/code and source JSON are not globally unescaped or altered. Markdown and HTML share activity rendering; CommonMark lists/tables and citation backlinks are preserved.
- Advanced chunk limits use compact numeric fields. Optional offline tokenizer limits use bundled data; cache misses fail rather than download assets. HTML/CSS previews, media/link grouping and tool details are described in the main README.
- Custom CSS can be selected, viewed read-only, copied and saved. The bundled default can also be viewed/saved. No CSS editor or generated JavaScript is required. Code/output blocks use ordinary CSS horizontal scrolling.

The window adapts vertically to advanced options and command wrapping, within the screen's visible bounds. Only overflow scrolls; the footer stays available. Equivalent command(s), Install CLI and Copy share their own group. The preview omits private GUI progress-protocol options.

## App-installed command line

Place the app in its final location, then use Install CLI to save an executable script named `extract-chat` in a writable directory on PATH. Save As grants permission to write that script only. The installer refuses existing files/symlinks, requests no administrator access, and does not edit shell profiles or strip quarantine. The app's executable-writing entitlement permits saving the selected launcher.

The script invokes this app's actual executable with its internal CLI dispatch switch and forwards arguments unchanged. Updating the app in place updates its CLI; moving/removing it requires saving a new launcher. A missing app returns 127. No separately installed companion or Python is needed; never run the inherited engine directly from Terminal.

The CLI uses ordinary arguments/defaults, not GUI conversion preferences. stdin/stdout, diagnostic bytes, exit status and INT/TERM/HUP forwarding are retained. App Sandbox changes cwd before Swift main, so the launcher captures its physical caller directory. The existing Python parser resolves file/glob, output, CSS, artifact, log and batch paths against it while internal libraries run in an accessible container. No caller-directory listing grant is required merely to launch an absolute-path command, and outputs must never be silently redirected into the app container. Plain Python CLI runs leave this private launcher contract unset and retain normal cwd behavior. See the [CLI reference](../docs/extract_chat.md) for options.

## File access and System Settings

The app declares standard Downloads read/write access and a Documents-only, home-relative read/write exception candidate. Both system privacy usage descriptions are bundled. **The Documents exception still requires App Review acceptance**; see [the exact scope and justification](APP-STORE-PREPARATION.md#documents-exception-for-app-review). It is not a grant for the whole home directory or arbitrary external locations.

macOS manages Files & Folders consent on actual Downloads/Documents operations. No custom folder selection is imposed on startup or CLI installation. The GUI does not replace a native privacy denial in those locations with its own picker. Help > File Access Settings… and access-failure details open System Settings and explain Privacy & Security > Files & Folders. The launcher/terminal may be the responsible application for CLI privacy attribution. No TCC database is inspected or edited, no privacy approvals are reset/enabled automatically, and Full Disk Access is not requested as a sandbox bypass.

Users can create a Documents subfolder for archives and results. CLI output directories are created when needed; the GUI's Beside each input default remains unchanged:

```sh
extract-chat --format both --managed-output \
  --output-dir "$HOME/Documents/Extract Chat" \
  "$HOME/Downloads/conversation.lgpt"
```

For other locations, File > Authorize Working Folders… and `extract-chat --grant-access [FOLDER]` remain explicit fallbacks. They use the standard macOS picker and remembered security-scoped bookmarks shared by GUI/CLI. With a path, select it or an ancestor; without one, select one or more folders. Cancellation returns 130 without extraction. `--list-access` lists those bookmark paths, not system privacy permissions. `--forget-access FOLDER` removes a bookmark, not system consent, files, ancestor grants or another process's active access. Existing grants survive conversion resets.

Normal CLI runs never open our configuration window or folder picker. macOS may ask on first protected-folder access; establish consent interactively before scheduling background jobs. Denial returns nonzero with recovery guidance. Revoked/stale grants, POSIX permissions, ACLs, symlinks, cloud providers and other system protections can still limit access. Missing glob matches can also indicate a typo or unavailable cloud file.

## Validation and release

The Python suite includes cross-platform packaging/assets and Markdown/HTML semantic parity checks. Native option, execution, window-sizing and CLI smoke tests live under `macos/Tests/`. `scripts/build_macos_gui_acceptance.sh` builds a signed, isolated-preferences host using the actual product view/model/runner. Keep this regression harness; obsolete packaging-only probes and standalone-companion builds are retired.

Private fixtures and review extracts remain outside Git. The single maintained review root is the existing compact preview, not a second source-check tree. Set `EXTRACT_CHAT_REVIEW_DIR` for optional private parity checks; never commit exported conversations or artifacts. Generated runtimes, dependency audits, evidence, caches and screenshots stay under ignored build/output paths.

The active icon master/provenance and all ten required macOS catalog slots are retained as source. Build outputs contain the MIT license and qualified third-party notices. About/Help point to the product support and policy pages; policy publication, clean-distribution consent/revocation, supported OS/architectures, privacy-manifest/reason-API review, final runtime compliance, signing/export and user acceptance remain release gates. See the submission checklist before archiving or uploading.
