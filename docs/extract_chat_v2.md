# Extract Chat V2 Architecture

This document describes the internals of the V2 pipeline that powers the
`extract-chat` CLI. The design replaces the original ad-hoc scripts with a
modular processor + formatter stack that supports Markdown, HTML, and Jekyll
outputs.

## Data Flow

```
JSON Export
   │
   ▼
ChatGPTConversation (Pydantic)
   │
   ▼
TurnProcessorV2  ──►  CitationProcessor
   │                    │
   ▼                    ▼
FormatterAdapter  ──►  Reference Payload Builder
   │
   ▼
Formatter (Markdown | HTML | Jekyll)
   │
   ▼
Rendered Output
```

- **ChatGPTConversation (`src/extract_chat/schemas/conversation.py`)** validates
  the raw JSON export and exposes helper methods for working with turns, messages,
  and metadata.
- **TurnProcessorV2 (`src/extract_chat/processors/turn_processor.py`)** walks the
  conversation mapping, orders turns chronologically, and produces normalized blocks
  of content (assistant/user/system/tool/etc.).
- **CitationProcessor (`src/extract_chat/processors/citation_processor.py`)**
  merges `citations` and `content_references`, assigns stable sequence numbers, and
  attaches metadata to each reference occurrence.
- **Reference Payload Builder (`src/extract_chat/processors/reference_processing/reference_utils.py`)**
  centralizes deduping, alphabetical backlinks, and stats consumed by every formatter.
- **FormatterAdapter (`src/extract_chat/processors/formatter_adapter.py`)**
  presents the processed blocks to whichever formatter the CLI selects.
- **Formatters (`src/extract_chat/formatters/`)** render the final output:
  - `markdown_formatter.py`
  - `html_formatter.py`
  - `jekyll_exporter.py`

The CLI entry point (`src/extract_chat/cli.py`) wires these pieces together and
handles command-line options.

## Key Features

- **Chronological Processing** – turns are ordered by timestamp while maintaining
  parent/child relationships so tool calls appear immediately after the assistant
  responses that triggered them.
- **Canonical Reference Payload** – shared builder assigns numbering/backlinks once so all formatters render identical alphabetical backlinks
- **Robust Citation Grouping** – references are deduplicated using normalized
  identity keys (URL + title/text + optional source label), ensuring consistent
  numbering across formats.
- **Reusable Block Model** – each conversation block contains enough metadata to
  render collapsible tool sections, system context, and window-shaded internal
  dialogue.
- **Consistent Formatting** – Markdown and HTML share the same reference layout;
  Jekyll exports reuse those anchors while splitting long articles across multiple
  pages.

## Jekyll Export Overview

The Jekyll exporter (`JekyllTurnExporter`) consumes the processed blocks for a
single assistant turn and emits:

1. Section pages (`{base-slug}-{sequence}.md`) that include front matter and
   forward/backward citation links using Jekyll’s `relative_url` helper.
2. A references page (`{base-slug}-references.md`) that aggregates all references
   and provides backlinks to each section anchor.

In addition, an audit report (`{base-slug}-reference-audit.md`) is dropped alongside the generated bundle so diagnostics stay with each export.

The CLI exposes this through:

```
extract-chat export.json \
  --format jekyll \
  --jekyll-turn-id <assistant-turn-id> \
  --jekyll-base-slug pa-paper \
  --output tmp/jekyll-pages
```

## Extending the Pipeline

- **New Formatters** can reuse the adapter output; implement the necessary render
  functions and plug them into the CLI (or a custom entry point).
- **Additional Metadata** can be surfaced by extending `TurnProcessorV2` to enrich
  the block dictionaries before they reach the formatter.
- **Citation Logic** lives in `formatters/reference_utils.py`; shared helpers ensure
  any new formatter maintains identical reference numbering/backlinks.

## Testing

`pytest` covers the processor, reference grouping, CLI flows, and the Jekyll
exporter. The tests rely on sample fixtures in `tmp/PA-Paper/`—keep those files
available when evolving the pipeline.
