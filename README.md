# extract-chat

Extract ChatGPT conversations from exported JSON files and render them as Markdown or HTML with proper citation handling.

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

## CLI Usage

```
extract-chat path/to/conversation.json -f markdown -o out.md
# or
extract-chat path/to/conversation.json -f html -o out.html
```

Options:
- `-f, --format`: `markdown` (default) or `html`
- `-o, --output`: Output file path
- `-c, --css-file`: Custom CSS path for HTML output
- `--force`: Overwrite existing output file

## Markdown Citations

- Inline markers in the model response like `` become a superscript link with an anchor at the citation site, e.g. `<sup id="cite-1_28_249_258"><a href="#ref-1_28_249_258">1</a></sup>`
- The References section renders entries per turn/reference with anchors like `<a id="ref-1_28_249_258"></a>` and includes a back-link `[↩︎](#cite-1_28_249_258)`

## HTML Citations

- The HTML formatter is currently being wired to match the Markdown citation behavior. Markdown is the primary, validated output.

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

