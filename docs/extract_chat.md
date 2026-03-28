# extract-chat CLI Reference

- [extract-chat CLI Reference](#extract-chat-cli-reference)
  - [Quick Start](#quick-start)
  - [CLI Options](#cli-options)
  - [Citations](#citations)
  - [Related Documentation](#related-documentation)
  - [Development Notes](#development-notes)
  - [Navigation](#navigation)

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

## Citations

Citations in the source JSON (`citations` and `content_references`) are merged into
single reference groups. Inline markers become superscript links (`<sup>1</sup>`)
that point to the globally numbered references list, while the shared payload builder
assigns alphabetical backlinks (`a^`, `b^`, …) to every occurrence. Assistant-provided
`**Sources:**` blocks are stripped before rendering so only canonical metadata reaches
Markdown, HTML, or Jekyll outputs.

## Related Documentation

- [README.md](/Users/mps/projects/AI-PROJECTS/extract-chat/README.md) – project overview and install paths
- [usage_examples.md](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/usage_examples.md) – practical workflows and examples
- [api.md](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/api.md) – Python/library usage
- [extract_chat_architecture.md](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/extract_chat_architecture.md) – internal pipeline and formatter architecture
- [media-bundle-contract.md](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/media-bundle-contract.md) – shared media bundle layout used with `LogGPT Plus`

## Development Notes

- Run the full test suite: `pytest -q`
- Committed fixtures used by tests live under `tests/fixtures/` and should remain synthetic or redacted.
- The CLI entry point is registered in `pyproject.toml` under `[project.scripts]`.

## Navigation

- [Back to README](/Users/mps/projects/AI-PROJECTS/extract-chat/README.md)
- [Usage Examples](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/usage_examples.md)
- [Python API](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/api.md)
- [Architecture Guide](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/extract_chat_architecture.md)
