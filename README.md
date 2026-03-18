# extract-chat

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](#) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Pydantic](https://img.shields.io/badge/Pydantic-2.0%2B-red)](#) [![UnicodeFix](https://img.shields.io/badge/UnicodeFix-Integrated-orange)](#)

`extract-chat` converts OpenAI and ChatGPT exported conversation JSON into readable Markdown or HTML conversation logs, with preserved citation links, schema diagnostics, and collapsible tool activity.

## What It Produces

- A normal user/assistant conversation transcript.
- A separate `System Context` section when the export contains reusable profile or instruction context.
- A per-assistant-turn `Tools Used` collapsible section that gathers tool calls and hidden/internal assistant activity in timestamp order.
- A per-assistant-turn `References` collapsible section with forward and backward citation links.
- Optional Jekyll page export for long assistant turns and reference bundles.

## Installation

Requires Python 3.10+.

```bash
pip install .
```

For development:

```bash
pip install -e .
```

Notes:

- The package import is `extract_chat`.
- The CLI entry point is `extract-chat`.
- HTML rendering uses the `markdown` package.
- Unicode normalization uses [`UnicodeFix`](https://github.com/unixwzrd/UnicodeFix), currently installed from GitHub.

## Quick Start

Markdown:

```bash
extract-chat path/to/conversation.json -o out.md
```

HTML:

```bash
extract-chat path/to/conversation.json --format html --output out.html
```

Jekyll bundle:

```bash
extract-chat path/to/conversation.json \
  --format jekyll \
  --jekyll-turn-id <assistant-turn-id> \
  --jekyll-base-slug my-conversation \
  --output tmp/jekyll-pages \
  --force
```

Batch validation run:

```bash
extract-chat \
  --batch-dir tmp/consolidated/JSON \
  --output tmp/batch-validate-20260318-archive-run \
  --batch-formats both
```

## CLI

Common options:

- `-f, --format`: `markdown` (default), `html`, or `jekyll`
- `-o, --output`: output file for Markdown/HTML, or output directory for Jekyll
- `-c, --css-file`: custom CSS file for HTML output
- `-v, --verbose`: enable debug logging
- `--log-file`: write logs to a file
- `--force`: overwrite existing files
- `--schema-warning-detail`: `summary` (default) or `full`
- `--media-index`: write a media inventory JSON file under a conversation-named subdirectory next to the output
- `-V, --version`: show the installed version

Batch options:

- `--batch-dir`: directory of JSON files to process in one validation run
- `--batch-formats`: `both` (default), `markdown`, or `html`
- In batch mode, `--output` is the run root directory and the tool creates `markdown/`, `html/`, and `reports/` under it

Jekyll-specific options:

- `--jekyll-turn-id`: assistant turn id to export
- `--jekyll-base-slug`: base slug for generated pages
- `--jekyll-layout`: front matter layout value
- `--jekyll-reference-title`: title for the references page

## Schema Diagnostics

`extract-chat` is Pydantic-first and tries to keep working when OpenAI export JSON drifts.

When the loader sees unexpected keys, content types, or incompatible shapes, it will:

- emit CLI warnings
- continue with fallback handling where possible
- write a schema exception report next to the output when warnings were raised

The report includes:

- package version
- encountered content types
- unknown top-level keys
- structured warnings with paths and representative turn ids

If you hit a schema variant that renders poorly or fails to parse, open a GitHub issue and attach:

1. the generated schema exception report
2. a redacted sample JSON fragment if possible

The CLI prints a prefilled GitHub issue URL for schema drift, and the generated schema exception report includes the same `issue_url` so reporters can jump straight into the repository issue tracker with the warning codes and content types pre-populated.

When warnings are raised, the tool also writes a `*-schema-issue.md` issue bundle next to the schema report. That file is designed to be uploaded or pasted into a GitHub issue without retyping the schema details from the terminal.

By default, schema warnings are summarized on stderr. Use `--schema-warning-detail full` if you want every warning entry printed to the terminal.

## Media Inventory

Use `--media-index` to generate a `media-index.json` file under a subdirectory named after the conversation stem. This does not download remote media; it inventories known media pointers, URLs, asset ids, and related attachment fields so a later pass can fetch them or link them into Markdown/HTML.

## Batch Validation Reports

Batch mode writes:

- `reports/summary.md` for human review
- `reports/results.csv` for machine analysis

The summary includes:

- total discovered files
- markdown/html success and failure counts
- files with schema warnings
- files with schema exception reports
- top warning codes
- top failure types

This is intended for validating mixed-era archives without writing back into the source tree.

## Citation Behavior

- Inline markers such as `` are replaced with superscript links in assistant text.
- Each assistant turn renders its own `References` section.
- References include backlinks to the citation site within that same assistant turn.
- Assistant-authored `**Sources:**` blocks are stripped from the primary Markdown and HTML transcript outputs so the canonical references come only from processed metadata.
- Jekyll export keeps a references page and a reference audit file for sectioned content.

## Output Model

Primary Markdown and HTML outputs follow this structure:

1. document metadata
2. optional `System Context`
3. visible transcript turns
4. per assistant turn:
   - `Tools Used`
   - assistant response body
   - `References`

This keeps the transcript readable while preserving provenance and research metadata.

## Project Notes

- `tmp/unified-output/` and `tmp/jekyll-pages-fix10/` contain reference outputs used as behavior guides, especially for citation integrity.
- Jekyll remains supported, but Markdown and HTML are the primary public outputs.
- JavaScript integration and referenced-media downloading are future work, not part of the current release.

## Development

Run tests with:

```bash
pytest -q
```

There is also a minimal GitHub Actions workflow that runs tests and a packaging smoke test on pushes and pull requests.

The tests cover:

- traversal and transcript shaping
- citation grouping and numbering
- Markdown/HTML reference parity
- CLI execution
- Jekyll export wiring

## License

MIT. See [LICENSE](LICENSE).
