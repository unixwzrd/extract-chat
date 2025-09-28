# extract-chat

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](#) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Pydantic](https://img.shields.io/badge/Pydantic-2.0%2B-red)](#) [![UnicodeFix](https://img.shields.io/badge/UnicodeFix-Integrated-orange)](#)

Extract ChatGPT conversations from exported JSON files and render them as Markdown, HTML, or Jekyll-ready sections with proper citation handling and reference management.

## Features

- **Multi-format Export**: Generate Markdown, HTML, or Jekyll-ready section pages
- **Intelligent Citation Processing**: Detects and processes inline citation markers like `【refId†Lstart-Lend】`
- **Advanced Reference Grouping**: Sophisticated two-step algorithm that properly groups references while preventing incorrect merging of distinct articles
- **Unicode Cleanup**: Integrated UnicodeFix for clean, professional output
- **Cross-page Citation Links**: Maintains working citation links across Jekyll section pages
- **Metadata Merging**: Combines data from both `citations` and `content_references` for complete reference information
- **Reference Title Prioritization**: Uses `source_label` when available, falling back to `title` for optimal display

## Installation

Requires Python 3.11+.

### Regular Installation

For normal usage:

```bash
pip install .
```

### Development Installation

For development work (editable install):

```bash
pip install -e .
```

This uses the `src` layout. The package name is `extract-chat` and the import is `extract_chat`.

The command line entry point exposed by the package is `extract-chat`.

## Quick Start

```bash
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

## CLI Usage

### Common Options

- `-f, --format`: `markdown` (default), `html`, or `jekyll`
- `-o, --output`: Output file for Markdown/HTML. For Jekyll, this should be a directory where the section pages will be written
- `-c, --css-file`: Custom CSS path for HTML output (optional)
- `--force`: Overwrite the destination if it already exists

### Jekyll-Specific Options

- `--jekyll-turn-id`: (Required when `--format jekyll`) Assistant turn identifier to export
- `--jekyll-base-slug`: Base slug used for generated filenames/permalinks. When omitted we attempt to derive one from the conversation title
- `--jekyll-layout`: Front-matter `layout` value for Jekyll pages (defaults to `page`)
- `--jekyll-reference-title`: Title used for the generated references page (defaults to `References`)

## Citation System

### Markdown Citations

- Inline markers in the model response like `【1†28:249-258】` become superscript links with anchors at the citation site
- Example: `<sup id="cite-1_28_249_258"><a href="#ref-1_28_249_258">1</a></sup>`
- The References section renders entries per turn/reference with anchors like `<a id="ref-1_28_249_258"></a>`
- Each reference includes a back-link `[↩︎](#cite-1_28_249_258)`

### HTML Citations

- HTML output mirrors the Markdown citation structure
- Superscript anchors link forward to the references section
- Each reference includes a backlink to the originating citation

### Jekyll Citations

- Cross-page citation linking using Jekyll's `relative_url` helper
- Stable cross-page links regardless of site base paths
- Separate references page with comprehensive citation management

## Reference Processing

The system includes sophisticated reference grouping and processing:

- **Two-step Grouping Algorithm**: Groups by `reference_title` with text preview, then merges groups with same `base_url` and short snippets
- **Reference Title Prioritization**: Uses `source_label` when available, falls back to `title`
- **Unicode Cleanup**: Integrated UnicodeFix for clean, professional output
- **Pipe Character Escaping**: Prevents Jekyll table interpretation issues

## Development

### Running Tests

```bash
# Run citation processor tests
python tests/test_citation_processor.py

# Generate reference report for a conversation
python tests/refs_report.py path/to/conversation.json

# Test formatter references
python tests/test_formatter_references.py

# Test Jekyll exporter
python tests/test_jekyll_exporter.py
```

### Project Structure

```
src/extract_chat/
├── cli.py                 # Command-line interface
├── processors/            # Citation and turn processing
│   ├── citation_processor.py
│   ├── turn_processor.py
│   └── formatter_adapter.py
├── formatters/           # Output formatters
│   ├── markdown_formatter.py
│   ├── html_formatter.py
│   ├── jekyll_exporter.py
│   └── reference_utils.py
├── schemas/              # Data models
│   ├── conversation.py
│   └── metadata.py
└── context/              # Document context management
    └── document_context.py
```

## Contributing

We welcome contributions! Here's how you can help:

1. **Bug Reports**: Found a bug? Please open an issue with:
   - Description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Sample JSON file (if applicable)

2. **Feature Requests**: Have an idea? Open an issue to discuss it

3. **Code Contributions**: 
   - Fork the repository
   - Create a feature branch
   - Make your changes
   - Add tests for new functionality
   - Ensure all tests pass
   - Submit a pull request

4. **Documentation**: Help improve docs, examples, or README

### Development Guidelines

- Follow the existing code style and patterns
- Add type hints for new functions
- Include tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

## Support This Project

If extract-chat has been useful to you, please consider supporting its development:

- [Patreon](https://patreon.com/unixwzrd)
- [Ko-Fi](https://ko-fi.com/unixwzrd)
- [Buy Me a Coffee](https://buymeacoffee.com/unixwzrd)

Your support helps maintain and improve this tool for everyone.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes and changes.

## License

Copyright (c) 2025 unixwzrd

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Python 3.11+ and [Pydantic](https://pydantic.dev/) for robust data validation
- Uses [UnicodeFix](https://github.com/unixwzrd/UnicodeFix) for comprehensive Unicode cleanup
- Integrates with [ftfy](https://github.com/rspeer/python-ftfy) for text normalization
- Designed for Jekyll static site generation
- Leverages modern Python type hints and data modeling