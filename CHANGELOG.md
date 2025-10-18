# Changelog

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
