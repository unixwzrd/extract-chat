# Changelog

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
