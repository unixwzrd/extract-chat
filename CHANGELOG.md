# Changelog

## 2025-09-25

- Skip citation entries that lack real metadata so the generated Markdown and HTML outputs no longer emit placeholder references such as `Metadata missing for ref_id …`.
- Added `bin/export_jekyll_sections.py` and supporting formatter utilities to split a single assistant turn into Jekyll-ready section pages plus a standalone references page, preserving working citation links across pages.
- Updated the Jekyll exporter so forward/backward citations use Jekyll's `relative_url` helper, keeping cross-page links stable regardless of site base paths.
- Added automated tests to ensure Markdown/HTML reference parity and to verify the Jekyll exporter’s cross-page citation wiring.
