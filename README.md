# extract-chat

Extract ChatGPT conversations from exported JSON files and render them as Markdown, HTML, or Jekyll-ready sections with proper citation handling.

- Parses parent/child conversation structure to preserve flow
- Detects inline citation markers like `【refId†Lstart-Lend】`
- Merges metadata from both `citations` and `content_references`
- Generates a single global References section
- Markdown: inline superscripts link forward to references, references link back to the in-text citations

## Installation

Requires Python 3.10+.

```
pip install -e .
```

This uses the `src` layout. The package name is `extract-chat` and the import is `extract_chat`.

The command line entry point exposed by the package is `extract-chat`.

## CLI Usage

```
# Markdown (default)
extract-chat path/to/conversation.json -o out.md

# HTML with optional CSS
extract-chat path/to/conversation.json --format html --css-file styles/site.css --output out.html

# Jekyll section export (writes multiple files into a directory)
extract-chat path/to/conversation.json \
  --format jekyll \
  --jekyll-turn-id c3df4f37-ab12-4ab6-a810-6b687a759b83 \
  --jekyll-base-slug 2025-09-25-pa-paper \
  --output tmp/jekyll-pages
```

Common options:

- `-f, --format`: `markdown` (default), `html`, or `jekyll`.
- `-o, --output`: Output file for Markdown/HTML. For Jekyll, this should be a directory where the section pages will be written.
- `-c, --css-file`: Custom CSS path for HTML output (optional).
- `--force`: Overwrite the destination if it already exists.
- `--jekyll-turn-id`: (Required when `--format jekyll`) Assistant turn identifier to export.
- `--jekyll-base-slug`: Base slug used for generated filenames/permalinks. When omitted we attempt to derive one from the conversation title.
- `--jekyll-layout`: Front-matter `layout` value for Jekyll pages (defaults to `page`).
- `--jekyll-reference-title`: Title used for the generated references page (defaults to `References`).

## Markdown Citations

- Inline markers in the model response like `` become a superscript link with an anchor at the citation site, e.g. `<sup id="cite-1_28_249_258"><a href="#ref-1_28_249_258">1</a></sup>`
- The References section renders entries per turn/reference with anchors like `<a id="ref-1_28_249_258"></a>` and includes a back-link `[↩︎](#cite-1_28_249_258)`

## HTML Citations

- HTML output mirrors the Markdown citation structure: superscript anchors link forward to the references section, and each reference includes a backlink to the originating citation.

## Development

- Run the simple processor test directly:

```
python tests/test_citation_processor.py
```

- Quick refs report for a full JSON export:

```
python tests/refs_report.py path/to/conversation.json
```

## License

Proprietary. All rights reserved.
