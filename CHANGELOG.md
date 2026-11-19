# Changelog

## 2026-11-19 — 1.0.0

GitHub source/support tag: `v1.0.0`. The native macOS build has been uploaded to App Store Connect; this source tag does not indicate App Store approval or public availability of the native app.

Known limitation: the inspected native build 1 validation/upload reports contain 91 missing-dSYM warnings for the embedded Python engine and native dependencies. The Swift app's dSYM is present and UUID-matched. Runtime symbol collection remains follow-up work; these warnings have not been fixed by the architecture or navigator changes. See [runtime symbol coverage](macos/APP-STORE-PREPARATION.md#runtime-debug-symbol-limitation).

- Repair the Xcode navigator's entitlements reference to the project-root signing file; the existing signed permissions are unchanged.
- Target Apple Silicon (`arm64`) in native Debug and Release builds by retaining Standard Architectures and excluding `x86_64` for macOS, matching the bundled engine even when the Architectures field returns to Standard. Intel/universal support is deferred; retain all engine architecture/signature checks.
- Refresh CLI, API, archive and macOS setup documentation, separating historical experiments from the current permission model and outstanding release gates. Explicitly package active native sources and synthetic fixtures, exclude deprecated local utilities, and keep private exports, backups and generated diagnostics out of Git.
- Declare native Downloads read/write access and a review-pending Documents-only sandbox exception, with system privacy usage descriptions and System Settings recovery for denied access. Remove automatic startup/install folder-selection prompts; retain explicit remembered-folder fallbacks for other locations. Preserve GUI destinations, original files and existing grants. Resolve CLI file options/default outputs against the captured caller directory without requiring access merely to enumerate that directory. Retire superseded packaging-only/standalone-companion experiments while retaining the product-view/native regression harness and private fixtures.
- Add Install CLI in the native command group to save an executable `extract-chat` launcher for the installed app's explicit CLI entry point. Reuse the embedded inherited-sandbox engine instead of requiring a separate companion, external Python, or GUI conversion preferences. Preserve caller-relative paths, quoting, streams/status/signals, existing commands and original inputs. Expose explicit fallback `--grant-access`, `--list-access` and `--forget-access` actions; ordinary conversions do not open the configuration window or our folder picker. CLI output options remain independent of permissions and GUI destinations.
- Accept ZIP-based `.lgpt` LogGPT Plus files in the CLI, native picker, Finder document opening and drops while preserving legacy ZIP/JSON support and archive safety. Register the custom type as LogGPT Plus file for Extract Chat with the product icon and primary viewer role; remain an alternate Open With choice for JSON/ZIP without taking their defaults.

### Transcript presentation and fidelity

- Make advanced numeric controls compact and readable, align Overlap and Files per upload batch on matching label/control rows, and group the command preview and Copy action. Strengthen visible-turn Markdown acceptance against HTML to compare order and actual semantic formatting, without requiring reasoning/tool disclosures in continuation content.
- Preserve intentional Markdown hard line breaks through Unicode cleanup by converting their trailing-space marker to the equivalent CommonMark backslash form outside code. The stricter formatting tests reproduce and guard the previous loss of breaks.
- Add rendered Markdown/HTML parity regression checks for all four source types, including ordered anchors, role/section headings, disclosures, body text, tool/code payloads, activity identity/time/model fields and citation/context/artifact destinations. Add deliberate-damage coverage and an opt-in private-extract audit; no private conversations are committed or fetched by tests.
- Keep code/tool output lines intact with horizontal scrolling rather than wrapping at dashes. Add a native read-only View CSS dialog with Copy and Save As for the active default/custom stylesheet; generate the bundled default from the engine's CSS source to avoid a separate theme copy.
- Remove unnecessary double-quote escapes directly in displayed JSON heredoc bodies, without adding a separate view or changing indentation, line breaks, other backslashes or the surrounding command. Preserve required JSON escapes, original source files and formatted/raw modes; never execute recorded code.
- Replace unresolved sandbox download links with explicit not-captured text, artifact failure details and conversion warnings. Resolve actual Markdown links without rewriting fenced/inline code; percent-encode local artifact URLs for filenames with spaces, Unicode and parentheses. Preserve source JSON and captured artifact bytes; never fabricate a missing file.
- Separate file/image/media artifacts from Related links, omitting web URLs already present in References. Keep citation references, source links and captured files distinct in HTML/Markdown.
- Advertise matched result counts on native tool calls and label the returned body Result / output. Match a namespace-only tool author to its explicit direct-parent call, without guessing across intervening nodes or timestamps. Retain unmatched source results and fix singular command/file-change captions.
- Interpret numeric citation publication timestamps as UTC dates, including epoch strings, instead of extracting misleading years such as 1774 from 2026 timestamps. Preserve conventional year/date strings and original source metadata.

- Narrow the index Time column from 35% to 25%, retain the Role column at 12%, and extend excerpts from 64 to 80 characters so Contents uses the recovered space without wrapping.

- Present stored-memory attribution as plain text rather than linking its title to personalization settings; retain working past-conversation links.
- Open standalone HTML outgoing links and captured image previews in new tabs with safe opener/referrer attributes, while retaining same-page index/citation navigation and explicit download behavior. Make local captured images clickable without changing their bytes or source JSON.
- Compact the optional conversation index with smaller single-line rows, date/time/zone labels without milliseconds/offset clutter, bounded excerpts and ellipses. Preserve full timestamp/excerpt tooltips and unchanged transcript content.

- Format native activity identity as labelled metadata fields (HTML definition grid / Markdown table), including actual author/tool, date, model, channel, message status and source node ID. Label grouped commentary accurately and shorten reasoning disclosure titles without dropping source text.
- Promote returned image-generation prompts, dimensions and generation parameters out of nested image metadata into readable tool-result and artifact sections. Associate the prompt's image link by exact asset identifier; preserve empty call arguments and source JSON, including literal backslashes and unavailable fields. Do not infer the image engine/version from a legacy metadata label.
- Show exported activity descriptions and explicit patch/diff/file-detail fields. Explain count-only work summaries and missing patch bodies rather than inventing filenames or change operations.

- Replace the flat native ChatGPT/Work activity dump with independently expandable reasoning, progress updates and paired commands/results, sharing one renderer between HTML and Markdown instead of duplicated formatter loops. Show assistant/activity model slugs, restore reasoning recap text, format exported thought summaries/content/chunks as prose, and retain relevant work/aggregate metadata under Exported fields. Do not infer missing reasoning or delegated-model identities.
- Render memory and past-chat attribution as Context used with titles, excerpts/reasons and safe absolute ChatGPT links; exclude those records from transcript media and the optional media inventory. They are context citations, not inferred tool runs.
- Attach activity using native parent ancestry without crossing user turns; preserve unanswered/orphan activity and unmatched calls/results. Pair tool outputs using the actual tool author and native links rather than the generic recipient `all` or timestamp adjacency. Preserve original JSON and existing Hermes presentation.

- Render exported conversation Markdown with CommonMark and table support so unordered/ordered/nested lists immediately following prose become actual HTML lists. Keep code fences literal and citation anchors intact; display transcript-provided executable HTML inertly. Declare the already-bundled MIT-licensed markdown-it-py renderer directly.
- Identify the selected tool-JSON display mode in transcript metadata. The default readable view decodes both argument and returned-result string fields once; formatted/original JSON views intentionally retain escapes.
- Retain the exact original conversation JSON under its original filename beside Markdown/HTML in native-app and managed CLI results, rather than renaming it `conversation-source.json`. Include the copy in safe-overwrite inventories and transactional publication/cancellation cleanup; preserve original ZIP and JSON inputs.
- Consolidate managed results into one folder with adjacent artifacts, manifests and optional media inventory/chunks. Read adjacent artifacts when reprocessing the retained JSON, while retaining legacy named-package input support. Copy only artifacts/manifests, not old renders or arbitrary sibling files; avoid empty derived-table directories. Preserve legacy non-managed CLI output layouts.
- Remove the References-specific left-padding override so its disclosure marker and label align with Media.
- Tighten default HTML paragraph, heading, disclosure and turn spacing. Stop treating inter-element HTML formatting whitespace as visible blank lines, preserve within-paragraph line breaks and code whitespace, and wrap long links.
- Put each answer's References before Media in both transcript formats, retaining forward/back citation anchors.
- Strip only `utm_source` from rendered HTTP(S) links and URL-only labels, without changing source JSON, code/tool payloads, local file paths, other query values or fragments.
- Add remembered Advanced Tool JSON choices and `--tool-json readable|pretty|raw`, shared by ChatGPT/Work, Hermes and continuity chunks. Keep readable fields plus collapsed Raw JSON as the default; offer indented escaped JSON or the original escaped JSON instead. Never unescape thoughts or ordinary code.
- Keep explicit final assistant answers visible even when their author provenance names a web tool. This restores replies previously folded into internal activity and keeps their citations and artifacts with the answer.
- Normalize modern ChatGPT inline citation widgets into linked source markers while retaining per-answer reference lists and native source metadata. Render named entity labels instead of opaque widget tokens.
- Group native same-exchange assistant progress updates beneath the final answer only when parent links confirm the sequence. Preserve progress text, tool activity, media and original turn anchors; do not combine sibling branches or unrelated replies.
- Recognize exported user/model context without requiring an optional system-message flag. Context absent from the source is not reconstructed.
- Separate role, turn ID and timestamp in transcript headers. Label local display times with the zone and UTC offset; add `--timezone` for UTC, IANA zones with historical DST, or fixed offsets. Source epochs and UTC-based filenames remain unchanged, including in continuity bundles.
- Add opt-in `--turn-index` collapsed navigation to Markdown/HTML. Expose and remember index/timezone choices in the native app, retaining prior settings compatibility and reset/cancel behavior.
- Visually group and indent advanced options separately from the equivalent command preview. The CLI launcher invokes the containing app, never the sandbox-inheriting engine directly.

### Readable tool payloads

- Replace the flattened field-by-field readable view with JSON-shaped output: preserve braces, arrays, quoted keys/values, indentation and comma-separated entries, but decode string newlines and quotes for human display. Keep actual literal backslashes intact and the original JSON collapsed; the display is not claimed to be machine-valid JSON.
- Align consecutive numbered file lines as `number | text`, including single-/double-digit transitions, while preserving code indentation and leaving unrelated pipe text alone. Keep `--tool-json readable` and saved settings compatible; rename the GUI choice to Readable JSON + Raw JSON.
- Display valid JSON tool arguments/results as JSON-shaped human-readable text, decoding one JSON layer so command newlines and quotes are readable while literal backslashes remain intact. Keep the original payload in a collapsed Raw JSON section in HTML and compatible Markdown viewers.
- Share the readable view across Hermes and existing ChatGPT/Work tool sections without blindly unescaping thoughts, prose or ordinary source code. Invalid, duplicate-key, nonstandard or excessively deep/broad JSON falls back unchanged. Escape HTML and size Markdown fences safely.
- Preserve the supplied ChatGPT, Work and Hermes examples as checksum-recorded private acceptance fixtures outside the application repository; do not commit conversation contents.

### Hermes Desktop input

- Add a dedicated, structurally recognized Hermes Desktop JSON adapter shared by CLI, ZIP, batch, continuity and native-app conversions. Validate the envelope, message identities/session membership, finite timestamps, roles and tool-call identifiers without weakening other source recognition.
- Retain inactive/compacted original messages, separate compression summaries from user dialogue, preserve native/provenance metadata and explicitly label summary-only or activity-only exports. Do not claim a derived Hermes timeline is a native branch tree or a complete recovered history.
- Render thoughts and paired tool arguments/results as independently collapsed sections in HTML and compatible Markdown viewers. Escape or safely fence payloads; do not execute commands or follow local paths from a chat export. Keep existing ChatGPT/Dots formatting unchanged.
- Document current chronological ChatGPT export behavior and defer branch exploration/selected-branch extraction to a separate milestone.

### First native macOS release preparation

- Assemble the isolated GUI acceptance app in a fresh staging bundle and verify it before publishing to its stable path; do not overlay signed helpers and retain removed dependency resources that invalidate their signatures.
- Explicitly use the product icon in permission/quit alerts and the extraction-details panel. Bundle the same icon into the isolated GUI acceptance host so its dialogs no longer show a generic placeholder.
- Exclude Xcode/SwiftPM generated and per-user state, diagnostic result bundles and Ruff caches while retaining shared schemes and release assets. Remove the obsolete tracked planning symlink, preserving local agent instructions as a standalone file without deleting the external planning archive.
- Explain missing output-folder access in a short native dialog before opening a plainly titled Select Folder picker. Remove the picker's long message banner; skip both dialogs when access is already available, remember granted access, and allow cancellation at either step without extracting or changing the destination.
- Raise the native app and GUI acceptance host minimum to macOS 14, with Info.plist following the configured deployment target. Review Xcode 27.2 settings, enable recommended diagnostics, weak references, dead-code stripping, string/asset symbol settings and validated build-script sandboxing. Retain the existing target-level signing team and the helper's compatible lower deployment minimum.
- Make the exit/cancel action state-aware: Quit with an empty queue or after a finished/failed/cancelled attempt; Cancel after actual queue edits or during extraction; Cancelling while cleanup is pending. Pending Cancel discards setup without quitting, active Cancel cooperatively stops the batch, and Quit exits without clearing completed results. Row selection and duplicate additions do not reset the finished state.
- Add a remembered Close on successful completion option (off by default). Quit only after the entire batch succeeds; keep the app open after cancellation, partial failure, setup errors or helper/protocol failures. Automatically open the failure-details dialog with affected file paths, reasons and engine diagnostics instead of requiring a separate Details action.
- Persist granted output-folder access using app-scoped bookmarks, restore it on later launches, and refresh stale bookmarks when possible. Keep access grants separate from output preferences and Reset to Defaults; do not repeatedly confirm an authorized destination or silently change it.
- Connect OK to actual bundled-engine extraction and open the app with an empty queue instead of an automatic file picker. Keep output beside each input by default and request parent-folder access when required by App Sandbox.
- Add live file stages/counters, queue progress, asynchronous stdout/stderr draining, cooperative cancellation, completed-result preservation, visible errors, diagnostic details and Show Results. Lock configuration and prevent duplicate jobs while extracting; normalize helper paths consistently with macOS URL aliases.
- Configure the development team and Apple Development automatic signing in both Xcode configurations, matching LogGPT, so ordinary builds no longer select ad-hoc signing and fail the engine identity check. Explain how to correct Sign to Run Locally if it is selected explicitly.
- Align the macOS application and Python engine at version 1.0.0, retaining app build number 1. The GitHub source/support tag is separate from App Store review approval and native-app availability.
- Add a dedicated Extract Chat product icon and all ten macOS standard/Retina asset slots, including 1024 pixels, with reproducible downsampling from the preserved master.
- Use the user's preferred ZIP archive artwork with a transparent exterior, preserve both originals, and explicitly load the bundled icon for About and the running app instead of relying on the placeholder-producing implicit lookup.
- Add Reset to Defaults for all GUI conversion options, output destination and CSS selection. Keep the selected input queue intact, save only on OK, and allow Cancel to restore previously accepted settings without changing files or existing results.

### macOS dependency qualification

- Add a reproducible dependency/notice inventory and native macOS deployment-target audit, with regression tests distinguishing deployment targets from unrelated dylib version numbers.
- Qualify a macOS-only tree-sitter-language-pack constraint to avoid a newer wheel's macOS 15 floor without changing UnicodeFix; retain the engine's macOS 13 baseline beneath the native app's macOS 14 minimum.
- Build a signed, nested-app Python helper with offline token data, native-library attribution, license notices, and a separate sandboxed real-archive packaging probe.

### Batch conversion and native interface

- Add a shared Xcode scheme, checked embedding of the signed Python runtime, an About panel with copyright/MIT and website links, and an explicit App Store preparation checklist. Privacy and Terms drafts live in the Jekyll site, not the app. The app remains in development and is not submission-ready.
- Grow the configuration window to fit expanded advanced options and wrapped command text, cap it at the current screen's usable height, and enable vertical scrolling only for overflow while keeping Cancel/OK visible.
- Accept multiple JSON/ZIP inputs and quoted glob patterns, with deterministic expansion and deduplication while retaining single-file and validation workflows.
- Add sequential managed jobs with numbered result folders, protected explicit overwrite, staged publication, per-file failure handling, cancellation cleanup, and opt-in structured progress.
- Add a native interface with multi-file input, remembered settings, grouped advanced options, input validation, and copyable shell-quoted commands. Finder document opening and drops use the same configuration queue as Add Files.

### Dots and source adapters

- Add a dedicated parser for LogGPT's versioned Dots main-timeline exports, including room-member authorship, deleted-message tombstones, embedded assistant text, and linked task references.
- Render Dots JSON and ZIP inputs through the existing Markdown, HTML, artifact-linking, and continuity-chunk pipelines.
- Recognize Dots `CalpicoFile_` attachment identifiers when linking locally packaged artifacts.
- Introduce a source-adapter registry and keep ChatGPT/Work normalization and diagnostics behind their own adapter. Unsupported formats fail explicitly; Hermes support awaits representative fixtures.
- Preserve native Dots message records and label the normalized chronological mapping as derived, not a native ChatGPT branch tree. Linked task and nested reply histories remain outside the capture scope.

### 2026-10-27 - Dependency compatibility

- Raise the minimum Python version to 3.11 to match UnicodeFix's requirements and align the CI matrix and installation documentation.
- Pin UnicodeFix to the tested revision `9e1cca9f9bb20139c258fe17c68ae7ee33391337` in both dependency declarations instead of following its moving default branch.

### 2026-10-27 - Context move instructions

- Remove the user-facing upload preamble from generated `context-move-instructions.md` files so the text begins directly with instructions for reconstructing the conversation context.

## 2026-10-03 - 0.7.8 - Transcript Fidelity and Timestamp Repairs

### Legacy export naming

- Accept mixed Unix-second and millisecond timestamps when generating dated conversation names and choosing the latest message date.
- Fall back to an unknown date for timestamps outside the supported calendar range instead of aborting the export.

### Transcript fidelity

- Preserve authored `Sources` blocks and `References` headings in Markdown and HTML, including headings inside pasted documents or code, instead of truncating the remainder of a message.

### Validation

- Add regression coverage for mixed timestamp units, invalid calendar dates, and preservation of authored source and reference sections in both transcript formats.

## 2026-10-03 - 0.7.7 - Portable Archive and Artifact Repairs

### ZIP extraction

- Recover older ZIP member names containing UTF-8 bytes without the UTF-8 flag only when the intended path is confirmed by the artifact manifest.
- Preserve files whose paths differ only by letter case by assigning distinct derived filenames, preventing overwrites on case-insensitive filesystems.
- Reject duplicate extraction destinations while retaining traversal and symlink protections.

### Artifact links and manifests

- Copy linked artifacts beside rendered Markdown and HTML even when the input and output share a filename stem, preventing links into temporary ZIP extraction directories.
- Preserve artifact directory structure when materializing local links.
- Update derived artifact manifests when package or artifact paths change, retaining original paths in `archive_relative_path` without modifying source ZIPs or JSON.

### Validation

- Add regression coverage for unflagged UTF-8 filenames, case-distinct artifacts, duplicate destinations, same-stem local links, and renamed manifest package roots.
- Update local media-link coverage to verify that rendered output references its materialized artifact copy.

## 2026-10-01 - 0.7.6 - ChatGPT Schema Compatibility

### Schema handling

- Accept ChatGPT's null `sectioned_conversation` placeholder without reporting schema drift.
- Report a dedicated warning if `sectioned_conversation` later contains data, while continuing to export from the canonical conversation mapping.

### Diagnostics

- Avoid repeating schema warnings when ZIP processing performs an internal metadata load before the export.
- Add regression coverage for null and non-null `sectioned_conversation` values and single-warning ZIP exports.

## 2026-09-18 - 0.7.5 - Chronology and Continuity Repairs

### Conversation ordering and rendering

- Render exported messages in stable timestamp order instead of conversation-tree preorder so older sibling branches cannot appear after newer turns.
- Display Unix timestamps as local time in `YYYY-MM-DD HH:MM:SS.nnn` format across Markdown and HTML output.
- Preserve a blank Markdown block boundary between complete turns in continuity chunks, including after media and tool `<details>` blocks.
- When `--force` regenerates a bundle with a different chunk count, remove obsolete numbered chunks for that same bundle without touching unrelated files.

### CLI help

- Separate chunk-boundary strategy from overlap mode in CLI help, display numeric operands explicitly, and document turn, line, byte, and no-overlap choices without presenting one as the preferred mode.
- Make the three overlap options mutually exclusive during argument parsing and retain one prior turn only as the fallback when no overlap mode is selected.
- Use single hyphens in canonical `YYYY-MM-DD-YYYY-MM-DD-title` names instead of empty-looking double separators.
- When a ZIP destination is not specified, write to a sibling directory matching its packaged conversation stem so exports sort chronologically even if the ZIP was renamed.

### Context handoff

- Generate `context-move-instructions.md` in every chunk directory using the actual chunk count, filenames, boundary strategy, overlap mode, byte ceiling, and upload plan.
- Add `--chunk-upload-batch-size FILES` so generated multi-batch instructions match the receiving service's current file limit without hand editing.
- Direct receiving models to deduplicate overlap, reconstruct working state without unsolicited summaries, preserve unresolved conflicts, treat archived instructions as historical rather than authorized actions, and report missing files exactly.

### Artifact copying

- Treat an already-materialized artifact with identical bytes as the same file instead of a forbidden overwrite when canonical output naming differs from the archive's internal JSON stem.
- Preflight genuinely different artifact collisions before writing rendered output, while continuing to require `--force` before replacing them.
- Report the complete packaged artifact count, split between newly copied and already materialized files, and report package metadata separately.

## 2026-09-14 - 0.7.0 - ChatGPT Work Compatibility

### ChatGPT Work support

- Recognize `sediment://` file pointers used by ChatGPT Work for generated and uploaded images.
- Reconnect Work image pointers to files captured in LogGPT Plus archives.
- Rewrite supported `sandbox:/workspace/scratch/` links to portable local artifact paths in generated Markdown and HTML.
- Recognize current ChatGPT Work conversation fields without emitting unnecessary schema-drift warnings.

### Validation

- Add regression coverage for Work image identifiers, workspace-linked artifacts, local artifact copying, and current Work schema fields.

## 2026-08-24 - 0.6.0 - LogGPT Plus Archive Support

### Archive and artifact handling

- Accept either a standalone ChatGPT conversation JSON file or a LogGPT+ ZIP archive as the CLI input.
- Safely extract ZIP archives while rejecting absolute paths, traversal, and symlink members.
- Copy generated, uploaded, and derived artifacts into a conversation-named output directory and prefer local artifact links in Markdown and HTML.
- Preserve original tabular artifacts while optionally rendering small CSV/TSV files inline or deriving TSV only when no downloaded equivalent exists.

### Output and continuity

- Add canonical output naming, combined Markdown and HTML export, and configurable destination and artifact directories.
- Add turn-aware Markdown chunking with optional overlap and a hard 524,288-byte maximum for ChatGPT uploads.
- Add a native macOS front end for selecting JSON or ZIP input and common export controls.

### Documentation and testing

- Document direct JSON and ZIP workflows, the LogGPT artifact archive contract, chunking behavior, and the macOS front end.
- Add regression coverage for archive safety, artifact discovery and rendering, table handling, canonical naming, and chunk-size enforcement.

## 2026-03-27 - 0.5.8 - Initial Public Release

### Tests

- Replaced the previous local/private reference fixture dependency with a committed synthetic conversation fixture under `tests/fixtures/`.
- Updated regression tests to load shared fixture paths from `tests/sample_data.py` instead of relying on workstation-specific `tmp/` files.
- Sanitized the committed synthetic fixture so personal/profile identifiers are removed while preserving realistic conversation structure and citation behavior.

### Maintenance

- Scrubbed lingering `tmp/PA-Paper` example paths from test helper scripts and replaced them with neutral synthetic fixture examples.

### Release

- Set the package version to `0.5.7` for the initial public release complementary to the `LogGPT` macOS Safari extension.

## 2026-03-22 — v0.5.0

### Refactor

- Reworked the transcript pipeline around a typed Pydantic render model.
- Changed Markdown and HTML outputs to render assistant turns with per-turn `Tools Used` and `References` collapsible sections.
- Attached internal/tool activity to the next visible assistant turn instead of emitting it as peer transcript content.
- Added local media bundle awareness so rendered transcripts can prefer files from `<stem>/media/` when a sibling media manifest is present.

### Schema Handling

- Added schema diagnostics for unexpected OpenAI export shapes and content types.
- Added automatic schema exception reports written next to output files when drift is detected.
- Updated CLI warnings to guide users toward filing GitHub issues with redacted samples for unsupported schema variants.
- Added optional duplicate-safe GitHub issue filing via `gh` for schema drift reports.

### Packaging

- Aligned package metadata around the MIT license.
- Added the `markdown` dependency for HTML rendering.
- Updated README positioning for Markdown/HTML-first public release behavior.
- Made `pyproject.toml` the authoritative packaging source while keeping `setup.py` as a minimal compatibility shim.

### Documentation

- Updated README coverage for schema issue filing, local media bundle consumption, and current known gaps.
- Added `docs/media-bundle-contract.md` to document the shared `LogGPT Plus` and `extract-chat` media layout.

## 2025-11-20 — v0.4.0

### Enhancements

- Added `-V/--version` flag and display of version in CLI help output.
- Clarified README/docs with the new version flag.

### Packaging

- Bumped project version to v0.4.0 in `pyproject.toml`, `setup.py`, and package metadata.

## 2025-11-06

### Bug Fixes

- Coerce numeric `async_status` values to strings during `Conversation` schema validation to match upstream exports.
- Reworked turn traversal to use iterative stacks, preventing recursion depth errors on deeply nested conversations.
- Added regression tests covering numeric `async_status` parsing and deep conversation traversal.

## 2025-10-18

### Reference Pipeline Cleanup

- Introduced a **canonical reference payload builder** that deduplicates metadata once and feeds the numbering/backlink data to every formatter.
- Switched Markdown, HTML, and Jekyll formatters to consume the shared payload so they now emit identical reference ordering and alphabetical backlink labels (`a^`, `b^`, ...).
- Centralized stripping of assistant-provided `**Sources:**` blocks so they no longer leak into Markdown/HTML exports and Jekyll sections.
- Updated the Jekyll exporter to drop the reference audit alongside the generated bundle, keeping diagnostics with each run.
- Added targeted tests covering the payload builder and formatter parity.

## 2025-09-28

### Major Improvements

- **Enhanced Reference Grouping Algorithm**: Implemented sophisticated two-step grouping logic that properly handles complex reference scenarios:
  - Groups references by `reference_title` (prioritizing `source_label` over `title`) with text preview to distinguish different articles
  - Merges groups with same `base_url` and short text snippets (≤200 characters) to handle cases like LinkedIn references
  - Prevents incorrect grouping of distinct articles from same domain (e.g., different ProPublica articles)
  - Optimized performance using string length instead of word count for short snippet detection

- **Unicode Handling Integration**: Added comprehensive Unicode cleanup for Jekyll export:
  - Integrated `unicodefix` package for aggressive Unicode normalization and cleanup
  - Added Jekyll-specific text cleaning method to handle zero-width spaces and problematic characters
  - Preserved Unicode characters in other contexts while ensuring clean Jekyll output
  - Updated dependencies to include `unicodefix @ git+https://github.com/unixwzrd/UnicodeFix.git`

- **Reference Display Improvements**:
  - Implemented `reference_title` field that prioritizes `source_label` when available, falling back to `title`
  - Updated all formatters and processors to use `reference_title` for consistent display
  - Added pipe character escaping (`|` → `\|`) specifically for reference titles to prevent Jekyll table interpretation
  - Enhanced reference metadata propagation throughout the processing pipeline

- **Jekyll Export Enhancements**:
  - Improved cross-page citation linking and reference organization
  - Better handling of reference grouping and deduplication
  - Cleaner Unicode output suitable for Jekyll processing

### Technical Changes

- Modified `CitationProcessor` to properly populate and use `reference_title` field
- Updated `reference_utils.py` with new two-step grouping algorithm and pipe escaping
- Enhanced `JekyllTurnExporter` with UnicodeFix integration for text cleaning
- Updated test scripts to use `reference_title` for accurate validation
- Optimized grouping performance by replacing word count with string length checks

## 2025-09-27

- Unified all command-line functionality behind the `extract-chat` console script
  registered in `pyproject.toml`; removed the legacy `bin/` wrappers.
- Added first-class Jekyll export support to the CLI with `--format jekyll` and
  associated options for turn selection, slugs, and page layout.
- Updated documentation (README, docs/) to reflect the new CLI usage and
  simplified architecture.

## 2025-09-25

- Skip citation entries that lack real metadata so the generated Markdown and HTML outputs no longer emit placeholder references such as `Metadata missing for ref_id …`.
- Added `bin/export_jekyll_sections.py` and supporting formatter utilities to split a single assistant turn into Jekyll-ready section pages plus a standalone references page, preserving working citation links across pages.
- Updated the Jekyll exporter so forward/backward citations use Jekyll's `relative_url` helper, keeping cross-page links stable regardless of site base paths.
- Added automated tests to ensure Markdown/HTML reference parity and to verify the Jekyll exporter’s cross-page citation wiring.
