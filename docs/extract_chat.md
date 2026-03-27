# extract-chat CLI

The `extract-chat` command converts a saved ChatGPT conversation export (.json) into
Markdown, HTML, or a bundle of Jekyll section pages while preserving turn order,
inline citations, and tool-call context.

## Quick Start

```bash
# Markdown (default)
extract-chat conversation.json --output conversation.md

# HTML with optional CSS override
extract-chat conversation.json --format html --css-file site.css --output conversation.html

# Jekyll section export (writes multiple files into a directory)
extract-chat conversation.json \
  --format jekyll \
  --jekyll-turn-id <assistant-turn-id> \
  --jekyll-base-slug 2025-09-25-pa-paper \
  --output tmp/jekyll-pages
```

## CLI Options

| Option | Description |
| --- | --- |
| `-f, --format` | Output format (`markdown`, `html`, `jekyll`). Default is `markdown`. |
| `-o, --output` | Destination file (Markdown/HTML) or directory (Jekyll). |
| `-c, --css-file` | Optional CSS file path applied to HTML output. |
| `-V, --version` | Show the installed `extract-chat` version and exit. |
| `--force` | Overwrite the destination if it already exists. |
| `--jekyll-turn-id` | Assistant turn identifier for Jekyll exports (required for `--format jekyll`). |
| `--jekyll-base-slug` | Base slug used for section filenames/permalinks (Jekyll). |
| `--jekyll-layout` | Front-matter layout for Jekyll pages (default `page`). |
| `--jekyll-reference-title` | Title used on the generated references page (default `References`). |

## Architecture Overview

```
JSON Export
   │
   ▼
TurnProcessorV2
   │   └─ groups turns chronologically, preserves tool calls & citations
   ▼
FormatterAdapter
   │   └─ presents processed blocks to the selected formatter
   ▼
Reference Payload Builder
   │   └─ deduplicates references & assigns alphabetical backlinks
   ▼
Formatter (Markdown | HTML | JekyllTurnExporter)
   │
   ▼
Rendered Output
```

Key components live under `src/extract_chat/`:

- `processes/turn_processor.py` – traverses the conversation mapping and produces
  structured blocks for each turn.
- `processors/citation_processor.py` – merges citation metadata and assigns
  stable sequence numbers.
- `processors/reference_processing/reference_utils.py` – shared helpers and the
  canonical reference payload builder consumed by every formatter.
- `formatters/markdown_formatter.py` – renders Markdown output with bidirectional
  references.
- `formatters/html_formatter.py` – mirrors the Markdown references and supports
  custom CSS injection.
- `formatters/jekyll_exporter.py` – splits a long-form assistant response into
  Jekyll-ready section pages plus a references page, keeping cross-page links intact.

## Citations

Citations in the source JSON (`citations` and `content_references`) are merged into
single reference groups. Inline markers become superscript links (`<sup>1</sup>`)
that point to the globally numbered references list, while the shared payload builder
assigns alphabetical backlinks (`a^`, `b^`, …) to every occurrence. Assistant-provided
`**Sources:**` blocks are stripped before rendering so only canonical metadata reaches
Markdown, HTML, or Jekyll outputs.

## Development Notes

- Run the full test suite: `pytest`
- Ensure the sample fixtures under `tmp/PA-Paper/` remain available if modifying
tests that exercise the Jekyll export flow.
- The CLI entry point is registered in `pyproject.toml` under `[project.scripts]`.
