# extract-chat Architecture

This document describes the internal pipeline that powers the
`extract-chat` CLI. The design replaces the original ad-hoc scripts with a
modular processor + formatter stack that supports Markdown, HTML, and Jekyll
outputs.

## Data Flow

Input JSON first passes through `extract_chat.adapters.parse_source`, which selects exactly one source adapter. `ChatGPTAdapter` owns legacy wrapper handling and existing ChatGPT/Work normalization and diagnostics; `DotsAdapter` validates the versioned `loggpt.dots` envelope and resolves authorship from room membership; `HermesAdapter` validates the Hermes Desktop export envelope and native messages, retains compacted originals, and separates compaction summaries from ordinary dialogue. Each returns `ParsedSource` with a canonical conversation and diagnostics to the common pipeline below. Unknown or ambiguous formats fail explicitly. Add another adapter and native fixtures for a new source rather than expanding a single parser. Hermes recognition is structural, not authentication of the producer; its desktop envelope has no format/version discriminator.

Hermes normalization preserves native records on canonical nodes and summary/envelope provenance in `source_metadata`. It emits separate thought and tool-request activity nodes, pairs results by request identifier, and explicitly labels summary-only or activity-only exports. Shared rendering keeps user/assistant text visible and produces independently collapsed, inert thought/tool payloads. Tool payloads are HTML-escaped or safely fenced; conversion does not execute them, read paths they mention or fetch referenced files. The normalized Hermes/Dots parent links describe derived timelines, not native branches.

`formatters.activity_details.render_json_payload` provides a shared display-only JSON-shaped view for valid JSON tool payloads. It parses one JSON layer and retains object/array boundaries, quoted keys/values and comma/newline-separated entries, while decoded string values show actual newlines/quotes. Continuation lines align with their string column; sequential numbered-file prefixes are spaced and right-aligned without erasing content indentation. The result need not parse as valid JSON: original text remains under Raw JSON and the retained source file. It never uses `unicode_escape` or global backslash substitution, and never applies decoding to reasoning. Duplicate object keys and nonstandard numeric constants are rejected for this view; depth/value-count limits cause a lossless raw fallback. Native ChatGPT/Work activity and derived Hermes activity remain source-aware presentation choices, not new parser forks.

`processors.native_activity` reads native thought summaries/content/chunks, reasoning recaps and context citations. It attaches activity to visible answers via parent ancestry without crossing user nodes, retains unanswered/orphan records, and pairs calls/results from matching tool authors and ancestry or explicit call IDs. A generic recipient of `all` is not a tool identity. Existing same-exchange progress grouping is retained, with model/context metadata carried on progress records. Context attribution becomes a separate linked Context used disclosure, not media or an inferred tool run. The common activity renderer replaces duplicated HTML/Markdown loops, displays each native activity independently under the assistant's Activity disclosure, and keeps useful work/aggregate fields expandable. Model slugs are shown on replies and activity records. The source export determines available reasoning, tool arguments and model identity; absent data is labelled, not reconstructed.

Conversation `parts` strings already contain decoded newlines after JSON loading. HTML rendering uses `MarkdownIt('commonmark')` with tables, rather than a Markdown dialect requiring a blank line before a list interrupting prose. Fences and inline code retain their meaning; generated citation HTML has a strict tag allowance and other transcript-provided HTML is escaped. Tool-return JSON is not treated as conversation Markdown: readable argument/result fields remain decoded inert text, with raw JSON retained separately. A mode caption distinguishes readable, formatted-escaped and original-escaped views.

### Result organization

Input discovery accepts conversation JSON and ZIP-based archives with .lgpt or legacy .zip extensions, case-insensitively. Both archive suffixes use the same safe extractor and source-format validation; changing an extension does not make arbitrary content valid. The native app exports ai.unixwzrd.loggpt.archive as LogGPT Plus file for Extract Chat and handles its document-open events through the existing queue, while JSON/ZIP remain alternate Open With types. Basic/standalone JSON and contained archive JSON are not converted to a proprietary JSON envelope merely to support the file association.

Sandbox artifact links are resolved as actual Markdown link destinations outside fenced/inline code, using the same destination parser as the CommonMark renderer. Captured file URLs are percent-encoded. Missing/failed captures retain their original locator and manifest failure reason as non-clickable artifact metadata and contribute an unavailable-artifact warning, not a schema-drift report. No missing file is fetched, recreated or substituted from another conversation. Display separates Artifacts from Related links and suppresses web URLs already in the citation reference list. Native tool-call headings report matched result counts; namespace-only tool authors require an explicit direct-parent call before grouping. Numeric publication epochs are converted to UTC years without modifying source citation metadata.

Managed jobs and the native app retain the source JSON bytes and filename; they do not emit normalized source files. Artifacts, manifests, optional media inventory and rendered documents share one result root, with an optional continuity subdirectory. Artifact discovery uses adjacent artifacts/manifests first, then legacy JSON-stem package directories. Copying is limited to artifact/media subtrees and package manifests, not an entire previous result. Manifest artifact paths in managed results are root-relative so staging/publication, numbered result folders and later reruns do not invalidate identifiers. The hidden result marker is only a safe-overwrite inventory; it is not required to parse a conversation. Reusable JSON display mode comparisons are test artifacts, not production outputs.

### Branch exploration (deferred)

ChatGPT exports can contain native `parent`, `children` and `current_node` relationships. These survive source parsing, but the current archive view renders all exported nodes chronologically, not only the current branch; regenerated answers may therefore appear next to each other. A future Chat Explorer/Branch Explorer could display that tree and export a selected endpoint by following parents back to the root and reversing the path, including all shared ancestors. Separate branch files could link to sibling paths while remaining self-contained with their preceding context. That is a separate application/milestone; branch selection, graph UI and branch-specific files are not implemented here, and no branch absent from the source can be recovered.

Presentation subsequently groups consecutive assistant commentary only when native exchange IDs match and the next visible component descends from the previous one without crossing a user node. The final component remains the main answer; earlier progress text moves into collapsed activity and media/turn anchors are retained. Siblings are not combined, and a component with its own reference table remains separate rather than losing citation context. Explicit visible final answers take precedence over tool-provenance heuristics such as `author.metadata.real_author = tool:web`.

ChatGPT modern citation widgets are normalized within the source adapter’s copied data into the existing reference pipeline, retaining native metadata and leaving the original input untouched. Formatters share display-only timezone conversion and stable per-turn anchors; optional collapsed indices link to those anchors. Source epochs, chronological ordering and UTC-derived filenames are not changed by display timezone settings. Context blocks require actual exported content, not assumptions about account settings.

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

- **Chronological Processing** – exported nodes are rendered in timestamp order. Native ChatGPT parent/child relationships remain available in the parsed data, but output is not a branch-selected transcript. Tool activity is associated with visible assistant turns; Hermes request/result payloads are grouped by request identifier.
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
exporter. The committed fixtures used by tests live under `tests/fixtures/` and
should remain synthetic or redacted when evolving the pipeline.
