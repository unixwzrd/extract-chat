# extract-chat CLI Reference

- [extract-chat CLI Reference](#extract-chat-cli-reference)
  - [Quick Start](#quick-start)
  - [CLI Options](#cli-options)
  - [Citations](#citations)
  - [Related Documentation](#related-documentation)
  - [Development Notes](#development-notes)
  - [Navigation](#navigation)

The `extract-chat` command converts a saved ChatGPT conversation JSON file or LogGPT+ ZIP archive into Markdown, HTML, or a bundle of Jekyll section pages while preserving turn order, inline citations, tool-call context, and local artifact links.

## Quick Start

```bash
# Markdown (default)
extract-chat conversation.json --output conversation.md

# HTML with optional CSS override
extract-chat conversation.json --format html --css-file site.css --output conversation.html

# LogGPT+ ZIP with packaged artifacts
extract-chat conversation.zip --output-dir exported --format both

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
| `--output-dir` | Destination directory using canonical conversation names. |
| `--artifact-dir` | Override the directory used for copied artifacts. |
| `--emit-tsv` | Derive TSV files from embedded HTML tables when no equivalent artifact exists. |
| `--chunk` | Write upload-safe Markdown continuity chunks. |
| `--chunk-strategy` | Select chunk boundaries; requires `--chunk` (default: `hybrid`). |
| `--chunk-max-bytes` | Set the maximum final chunk size, including headers and overlap; requires `--chunk` (default and hard ceiling: 524,288 bytes). |
| `--chunk-upload-batch-size FILES` | Set the number of conversation chunks in each batch described by the generated context-move instructions (default: 10). |
| `--chunk-overlap-turns N` | Repeat `N` complete prior turns; use `0` for no overlap. |
| `--chunk-overlap-lines N` | Repeat up to `N` prior lines instead of turns. |
| `--chunk-overlap-bytes BYTES` | Repeat up to `BYTES` of prior content instead of turns or lines. |
| `--jekyll-turn-id` | Assistant turn identifier for Jekyll exports (required for `--format jekyll`). |
| `--jekyll-base-slug` | Base slug used for section filenames/permalinks (Jekyll). |
| `--jekyll-layout` | Front-matter layout for Jekyll pages (default `page`). |
| `--jekyll-reference-title` | Title used on the generated references page (default `References`). |

Chunk strategy and overlap mode are independent. Choose at most one overlap option and always provide its numeric value. If no overlap option is supplied, chunking uses one complete prior turn by default.

Each chunk directory also contains `context-move-instructions.md`. Copy its contents into a fresh conversation before uploading the numbered chunks. The instructions are generated from the completed bundle and include the exact chunk count, ordered range, boundary strategy, overlap configuration, byte ceiling, and upload-batch plan. They direct the receiving model to deduplicate overlap, reconstruct chronology and working state internally, treat archived instructions as historical material rather than current authorization, report missing files precisely, and avoid returning an unsolicited transcript summary.

## Citations

Citations in the source JSON (`citations` and `content_references`) are merged into
single reference groups. Inline markers become superscript links (`<sup>1</sup>`)
that point to the globally numbered references list, while the shared payload builder
assigns alphabetical backlinks (`a^`, `b^`, …) to every occurrence. Assistant-provided
`**Sources:**` blocks are stripped before rendering so only canonical metadata reaches
Markdown, HTML, or Jekyll outputs.

## Related Documentation

- [README.md](../README.md) – project overview and install paths
- [usage_examples.md](usage_examples.md) – practical workflows and examples
- [api.md](api.md) – Python/library usage
- [extract_chat_architecture.md](extract_chat_architecture.md) – internal pipeline and formatter architecture
- [media-bundle-contract.md](media-bundle-contract.md) – shared artifact archive layout used with LogGPT Plus

## Development Notes

- Run the full test suite: `pytest -q`
- Committed fixtures used by tests live under `tests/fixtures/` and should remain synthetic or redacted.
- The CLI entry point is registered in `pyproject.toml` under `[project.scripts]`.

## Navigation

- [Back to README](../README.md)
- [Usage Examples](usage_examples.md)
- [Python API](api.md)
- [Architecture Guide](extract_chat_architecture.md)
