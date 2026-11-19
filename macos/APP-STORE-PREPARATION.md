# Extract Chat: Xcode and App Store preparation

Status: GitHub source/support version 1.0.0, November 19, 2026. Native app build 1 has been uploaded to App Store Connect and appeared in TestFlight with its product icon; the user reports completing export compliance. This does not establish App Store review approval or public availability. Development builds/local acceptance do not close the remaining distribution gates, and this document does not authorize further uploads, review submissions or publication.

## Current architecture

One sandboxed application provides the GUI and an explicit CLI entry point. Both use the same embedded frozen Python engine at `Contents/Helpers/ExtractChatEngine.app`. There is no separately installed CLI companion, external Python requirement, PATH fallback to a developer installation, or direct Terminal execution of the inherited engine. Install CLI saves a small executable `extract-chat` launcher for the containing app; updating that app in place updates its CLI. See [app-installed command line](README.md#app-installed-command-line) for installation, folder permissions, normal CLI options and recovery commands.

The initial native release targets Apple Silicon (`arm64`) on macOS 14 or later, explicitly configured for both Debug and Release. The GUI acceptance host has the same platform minimum. The frozen helper retains its macOS 13 compatibility baseline. Intel/universal support is deferred to a later release, not a gate for this Apple Silicon release; it requires a matching qualified engine and native dependencies before widening the target architectures. Do not claim Intel support or bypass the embedded-engine architecture check. App Sandbox and Hardened Runtime remain enabled. The engine has exactly the sandbox and inherit entitlements; the containing app declares Downloads read/write, the Documents-only exception candidate below, user-selected read/write, executable-writing and app-scoped bookmarks.

The app retains `ARCHS = $(ARCHS_STANDARD)` and sets `EXCLUDED_ARCHS[sdk=macosx*] = x86_64` for both Debug and Release. The resulting Archive architecture is `arm64` even when Xcode displays Standard Architectures (Apple silicon, Intel). Check the exclusion and effective build settings rather than that label alone. Apple documents [Excluded Architectures](https://developer.apple.com/documentation/xcode/build-settings-reference#Excluded-Architectures) as removing unsupported architectures from `ARCHS`, including when a higher-level setting overrides it. A future universal release must remove this exclusion only after qualifying its matching engine/dependencies; the engine architecture check remains unchanged.

The earlier custom first-run/install folder-selection offer has been removed. On real Downloads/Documents operations, macOS manages privacy consent using the bundled usage descriptions. Access failures explain Privacy & Security > Files & Folders and offer Open System Settings; Help > File Access Settings… also opens the system application. File > Authorize Working Folders… and `extract-chat --grant-access` remain explicit fallbacks for other paths. Existing bookmarks remain usable and conversion resets preserve them. No permission approval, TCC reset, TCC-database edit, or Full Disk Access grant is performed automatically. For CLI jobs, the system may attribute privacy access to the launcher/terminal application; establish consent interactively before scheduling background work.

## Documents exception for App Review

This is a signed development candidate, not a granted App Store exception. The sole requested filesystem exception is `com.apple.security.temporary-exception.files.home-relative-path.read-write`, with one array entry, `/Documents/`. Downloads uses the standard `com.apple.security.files.downloads.read-write` entitlement. No exception requests `/`, the whole home directory, Desktop, external volumes, or arbitrary system files. The inherited engine must not duplicate these keys; it inherits the containing app's static sandbox.

App Sandbox Entitlement Usage Information can be based on these concrete requirements:

- Purpose: Extract Chat converts user-owned LogGPT JSON/LGPT/ZIP conversation exports and preserves their accompanying artifacts as local Markdown/HTML and optional continuation chunks.
- Location: Documents is the conventional user-controlled workspace. Users can create a subfolder such as Documents/Extract Chat for input archives and results, including multiple distinct workspaces beneath Documents.
- Read/write need: read selected archives, adjacent manifests/artifacts and optional CSS; create managed results, preserve exact source JSON/artifact bytes, stage transactional batch output and write requested logs/reports. Read-only access does not support these output operations.
- Workflow: the bundled `extract-chat` command supports background runs, batches and scripts without displaying a folder-selection dialog for every new Documents subdirectory. The GUI and CLI use the same sandboxed embedded engine; CLI arguments, not GUI preferences, determine output destinations.
- Assessment: on a clean distribution installation, authorize Downloads/Documents through the system privacy prompt, then run GUI extraction and CLI batch/script commands from another directory using inputs/output subdirectories in Documents. Deny/revoke system access and confirm a nonzero failure with Settings guidance, no substituted destination, and unchanged originals. Verify the expected first-access privacy attribution for both GUI and the supported terminal/launcher.

Apple requires entitlement usage information for each exception and a Feedback Assistant report ID when this works around a missing App Sandbox feature. No report ID has been invented or submitted by this work. The user must review the justification, file the applicable report, and obtain App Review acceptance before treating this candidate as a releasable App Store permission model. If the exception is declined, choose an explicit alternative; do not silently widen access or disable sandboxing. See [Apple's submission requirements](https://developer.apple.com/help/app-store-connect/reference/app-uploads/app-sandbox-information).

The GUI opens with an empty queue. Add Files, File > Open, drops and Finder document events feed the same managed-job queue. OK runs the embedded engine with structured progress, per-file errors, cancellation and Show Results. Results default beside each input, inside a managed per-input folder; missing permissions must not silently redirect output. Overwrite applies only to intact managed results, with transactional publication and cancellation cleanup. Original inputs, named source JSON and captured artifacts are preserved. The footer switches between pending/active Cancel, disabled Cancelling and idle/finished Quit. Close on successful completion defaults off and never closes a failed or cancelled batch.

## Supported input and rendering

- ChatGPT, ChatGPT Work and Dots exports, plus structurally recognized Hermes Desktop JSON. Synthetic source fixtures remain offline and committed; real private samples remain outside Git.
- JSON, legacy ZIP and ZIP-based LGPT archives share format validation and safe extraction. The exported `ai.unixwzrd.loggpt.archive` type is described as LogGPT Plus file for Extract Chat. JSON/ZIP remain alternate Open With types rather than taking their existing defaults.
- Markdown is first-class. Visible-turn acceptance compares semantic formatting and role/order/text with HTML; separate tool/reasoning activity is not required for context-continuation fidelity. Additional checks cover citations/backlinks, artifact destinations, disclosure order and activity metadata.
- Thoughts, progress, calls and associated results use shared normalization/rendering. Exported image prompts, context citations and count-only work summaries are presented without inventing missing tool payloads, patch bodies, files or model identities. Unavailable artifacts are labelled rather than linked to nonfunctional sandbox URLs.
- Local/default CSS is viewable, copyable and saveable without an editor. Tool JSON display modes preserve original source JSON. Code/output blocks use CSS and ordinary HTML scrolling, with no generated JavaScript requirement.

## Build in Xcode

1. Open `macos/ExtractChatApp/ExtractChatApp.xcodeproj`, select the shared ExtractChatApp scheme and My Mac.
2. Keep the existing automatic signing, App Sandbox and Hardened Runtime settings. The selected team is `69H57JTW3S`, matching LogGPT. Other developers must select their own team. Do not select ad-hoc Sign to Run Locally while embedding a certificate-signed engine.
3. Build the frozen engine in the isolated qualified environment using `scripts/build_macos_helper.sh`, with `EXTRACT_CHAT_SIGN_IDENTITY` matching Xcode. Rebuild after Python/dependency changes. Xcode embeds the prepared engine; it does not install Python packages or download dependencies during builds.
4. Xcode checks engine signatures, entitlements, notices, offline tokenizer data and architectures before embedding the complete nested app under Contents/Helpers. Do not bypass these checks to produce a nominal universal archive without a qualified Intel engine.
5. Stop an old development run before manually testing new code; an already-running process retains its previous implementation. About contains the MIT license, `Copyright 2026 Distributed Thinking Systems LLC.`, and website/policy links. Help opens the corresponding website pages.

SwiftPM is a fast compilation check, not a signed app bundle or a substitute for Xcode/sandbox acceptance. Release signing requires matching signatures throughout the engine/native libraries, not just re-signing the outer app. Validate the eventual exported package separately.

## Validation and retained evidence

Keep the native regression suites under `macos/Tests/`, the actual product-view sandbox host built by `scripts/build_macos_gui_acceptance.sh`, dependency audits and the Python suite. The obsolete packaging-only probe, direct-helper CLI prototype and standalone-companion build path have been retired. Generated experiments, app bundles, logs, caches and screenshots are not source deliverables.

The November 19 pre-onboarding baseline passed 261 Python tests with one optional private-fixture skip, native option/CLI smoke tests, Xcode Debug, SwiftPM and strict recursive signature validation. The GUI-saved 0755 launcher ran from Terminal with PATH restricted to `/usr/bin:/bin`. Separate CLI processes reused picker-granted folders; a different unauthorized output folder failed without redirection. Cancellation preserved grants, forgetting a test grant caused a subsequent write denial without changing existing results, and SIGTERM reached the engine with status 143. First-run onboarding has additional focused tests; record fresh results when qualifying a release rather than treating dated counts as current.

The earlier first-run-picker experiment passed its local tests but has been superseded by system-managed Downloads/Documents access. Do not use those earlier picker receipts to claim native privacy-consent or distribution qualification. Current validation must include caller-relative input/glob/output/CSS/log/batch paths without home-directory bookmarks, absolute input paths from an otherwise unauthorized cwd, JSON defaults and Jekyll/chunk/batch output placement, and preservation of the plain Python CLI behavior.

The November 19 system-access candidate passed 268 Python tests with one optional private-fixture skip, all four private Markdown/HTML parity cases, native option/permission classification and launcher/conversion/chunk smoke checks. The frozen engine was rebuilt and signed; its native dependency audit had no blockers. Xcode Debug and strict recursive signature verification passed, and the built app contains the two usage descriptions, standard Downloads entitlement and exactly the Documents-scoped exception. The inherited helper keeps its two original sandbox/inherit keys.

A freshly identified signed host with no saved folder bookmarks converted inputs in Documents and Downloads, including caller-relative multi-file jobs launched from the home directory and an absolute-path job launched from the project directory. GUI extraction in Documents completed without the custom output-folder picker. Unauthorized default outputs failed without any app-container substitute, and synthetic originals were unchanged. These demonstrate local sandbox scope and path handling, not clean-distribution TCC prompt attribution or denial/revocation behavior: no privacy database was inspected/edited, no existing approvals were reset, and no system privacy permission was enabled automatically. Those privacy tests and App Review acceptance remain outstanding.

Private ChatGPT, refreshed Work, Hermes and Dots fixtures are retained under `/Users/mps/projects/AI-PROJECTS/GPT_Chats/consolidated/private-fixtures/extract-chat/2026-11-18`. Existing review extracts are refreshed in place under `consolidated/tmp/extract-chat-compact.yprOU0`; do not create another competing review directory or commit private contents. Prior real-source qualification preserved original JSON and all 39 captured artifacts, and matched the eight reviewed HTML/Markdown files. Missing upstream artifacts remain unavailable; do not reconstruct or fetch them merely to make tests pass.

Dependency and frozen-runtime audits are described in [DEPENDENCY-AUDIT.md](DEPENDENCY-AUDIT.md). The isolated environment, prepared engine, tokenizer cache, notices and detailed local logs are under ignored `build/macos-qualification/`. Keep failed dependency findings as evidence; they are distinct from the corrected shipped-runtime candidate. Never delete private fixtures, review overlays/backups, or the qualified runtime environment as incidental experiment cleanup.

The November 19 commit-cleanup check passed 269 Python tests with one optional private-fixture skip, all four private parity cases, native option/execution/window smoke tests, SwiftPM, Xcode Debug and strict recursive app-signature verification. The same Python suite passed from a freshly unpacked source distribution. Wheel/source archives excluded deprecated local utilities and generated/private state; the source archive included the active native build sources, icon assets and synthetic fixtures. These are source/development checks, not distribution or App Review approval.

The November 19 architecture follow-up completed an actual development-signed Archive in a separate ignored validation directory with the Mac-only Intel exclusion, not a command-line architecture override. The archived application is arm64, the engine check passed unchanged, and strict recursive signature verification passed. The Python suite passed 270 tests with one optional private-fixture skip. This is not App Store export/upload validation or approval of the Documents entitlement. The architecture exclusion must remain visible in both the saved project and the open Xcode target settings.

## Runtime debug-symbol limitation

The inspected version 1.0.0/build 1 validation and upload reports contain the same 91 missing-dSYM warnings for the embedded Python engine and its native libraries/extensions. The archive includes a UUID-matched dSYM for the main Swift app. The symbol warnings are distinct from binary upload success, icon processing and entitlement signing; upload receipts show success and the user confirmed the processed TestFlight build. They have not been resolved by re-archiving or the architecture/navigator fixes.

Follow-up: obtain UUID-matched vendor symbols or rebuild the runtime/native dependencies with debug information, preserve those dSYMs through packaging, collect them into the Xcode archive and verify coverage against every shipped Mach-O UUID. The inspected engine and representative Python/Pillow/Pydantic binaries have no DWARF segment or debug-map object entries from which to regenerate full debug information. Merely changing the Swift app's Debug Information Format or rerunning `dsymutil` on stripped components does not supply that missing information. Retain the actual uploaded archive and existing symbols. See [Apple's symbol guidance](https://developer.apple.com/documentation/xcode/building-your-app-to-include-debugging-information).

## Policy drafts and website handoff

The website is the policy source of truth; no duplicate Privacy/Terms reader or policy copy is bundled. The product links target:

- Support: `https://unixwzrd.ai/projects/extract-chat/`
- Privacy: `https://unixwzrd.ai/Policies/Privacy_Extract_Chat/`
- Terms: `https://unixwzrd.ai/Policies/Terms_Extract_Chat/`

Live unauthenticated checks on November 19 found the support page reachable, but both policy URLs returned HTTP 404. Their publication is an outstanding submission gate, not completed website work.

The editable drafts are `html/Policies/Privacy_Extract_Chat.md` and `html/Policies/Terms_Extract_Chat.md` in `/Users/mps/projects/AI-PROJECTS/DTS-WebSite/unixwzrd.github.io`. They were staged with `published: false` and reviewed with Jekyll's `--unpublished`; check their current status before publication. Approve wording, add an effective date and verify live unauthenticated URLs before supplying release metadata. Preserve unrelated website/LogGPT edits. No deployment is authorized by this application task.

Keep the repository MIT notice and bundled third-party notices. Website Terms explain usage rather than restricting MIT rights; App Store license-agreement metadata is a separate submission decision. Policy wording must distinguish local processing, optional support correspondence, local diagnostics and third-party folder-provider synchronization. Do not claim that local conversion eliminates every security risk or all privacy obligations.

For the Jekyll handoff, review consistent support/contact, documentation, availability, licensing, policies and purchase/refund routes across products without imposing a single license or business model. Distinguish public issues from private support for sensitive conversation archives; use the stable product support URL to route users without requiring an app update.

## App Store screenshots

To do before submission: prepare actual-product screenshots framed for the Mac App Store, not arbitrary window-sized captures. Apple's [screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/) list 16:10 Mac images at 1280 × 800, 1440 × 900, 2560 × 1600 or 2880 × 1800 pixels, with one to ten screenshots in JPEG/JPG/PNG format. Recheck the requirements at upload time. Use opaque RGB exports; retain high-resolution originals privately.

Plan a consistent 2880 × 1800 set, with short captions and readable app content at thumbnail size. Capture a small, focused set rather than shrinking the fully expanded advanced-options window until its text is illegible:

- Main extraction window with a small synthetic multi-source queue and basic options visible; make this the lead image.
- Actual rendered HTML showing readable turns, a captured artifact, citations and conversation navigation. Clearly distinguish browser-rendered output from the native app.
- Activity disclosures showing an exported tool call/result and image prompt, using synthetic/non-sensitive content.
- Optional advanced-options/CLI-install view if it remains readable and adds useful information.

Use only implemented features in the release being submitted; do not depict the future embedded-app/chart support as available. Exclude real conversations, names, financial data, private paths and unrelated desktop/browser chrome. Check exact pixel dimensions, aspect ratio, no transparency, clipping, caption legibility and small-thumbnail readability before upload. This is a planned asset task; no screenshots have been captured or submitted by this checklist entry.

## Remaining release gates

- Qualify actual supported OS versions and architectures, clean installation, the signed distribution export, offline operation, cloud providers, stale/moved/revoked bookmarks and large/cancelled jobs. Local Apple Silicon development acceptance does not establish these.
- Re-run all four private source samples and follow captured artifact links for the final release. Preserve originals; do not confuse successful synthetic tests or an older private acceptance receipt with current live-export acceptance.
- Finish the final shipped-runtime license/notice reconciliation, source-availability obligations, tokenizer redistribution and required-reason API/privacy-manifest audit, including native code. Retain the complete ten-slot macOS icon asset set and review final artwork/document handling.
- Approve/publish support and policy pages, screenshots, description, pricing, export compliance and review instructions. Reconcile App Privacy answers with actual bundled components and release behavior. The intended model is no developer collection of conversation data, tracking or automatic diagnostic uploads.
- Only with separate authorization: archive, validate and upload through Xcode Organizer. Development signing/build success does not authorize commits, tags, publication, billing changes or submission. App Store export and independent Developer ID notarization are separate distribution workflows.

## Apple references

- [Accessing files from App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox)
- [Full Disk Access does not bypass App Sandbox: Apple DTS](https://developer.apple.com/forums/thread/807142)
- [Embedding a command-line tool in a sandboxed app](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app)
- [Privacy policies: App Review Guideline 5.1.1](https://developer.apple.com/app-store/review/guidelines/#data-collection-and-storage)
- [Manage App Privacy](https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy)
- [Standard EULA and custom license agreements](https://developer.apple.com/help/app-store-connect/manage-app-information/provide-a-custom-license-agreement)
