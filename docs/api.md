# extract-chat Python API

This page covers the supported programmatic usage of `extract-chat`.

Most users will use the `extract-chat` command-line tool. If you want to integrate the library into your own scripts or pipelines, the most useful building blocks are:

- `Conversation` for loading and validating exported JSON
- `DocumentContext` for shared conversation helpers
- `TurnProcessorV2` for converting raw conversation data into a typed render document
- `MarkdownFormatter` and `HTMLFormatter` for rendering output
- `JekyllTurnExporter` for exporting a single assistant turn as Jekyll pages

## Load and Validate a Conversation

```python
from pathlib import Path

from extract_chat.schemas.conversation import Conversation

json_path = Path("conversation.json")
conversation = Conversation.model_validate_json(
    json_path.read_text(encoding="utf-8")
)
```

You can also validate an already-loaded Python dictionary:

```python
import json

from extract_chat.schemas.conversation import Conversation

payload = json.loads(Path("conversation.json").read_text(encoding="utf-8"))
conversation = Conversation.model_validate(payload)
```

## Build a Render Document

The processor turns a `Conversation` into a typed `RenderDocument` with:

- visible transcript turns
- system context entries
- assistant-attached tool activity
- per-turn references tables

```python
from extract_chat.context.document_context import DocumentContext
from extract_chat.processors.turn_processor import TurnProcessorV2

DocumentContext.initialize(conversation=conversation)
try:
    document = TurnProcessorV2().process_conversation(conversation)
finally:
    DocumentContext.reset()
```

## Render Markdown

```python
from extract_chat.formatters.markdown_formatter import MarkdownFormatter

markdown = MarkdownFormatter().format_document(document)
```

## Render HTML

```python
from extract_chat.formatters.html_formatter import HTMLFormatter

html = HTMLFormatter().format_document(document)
```

If you want custom CSS:

```python
html = HTMLFormatter({"css_file": "site.css"}).format_document(document)
```

## Export a Single Assistant Turn to Jekyll

Jekyll export is single-turn oriented. You must provide one assistant `turn_id`.

```python
from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.jekyll_formatter import JekyllTurnExporter

DocumentContext.initialize(conversation=conversation)
try:
    exporter = JekyllTurnExporter(base_slug="my-conversation")
    sections, references_page = exporter.export_turn(
        conversation=conversation,
        turn_id="assistant-turn-id",
        reference_page_title="References",
    )
finally:
    DocumentContext.reset()
```

Each `section` and the `references_page` is a `JekyllPage` object with:

- `title`
- `slug`
- `filename`
- `permalink`
- `content`

## Convenience Formatter Imports

The formatter package exposes a few convenience imports:

```python
from extract_chat.formatters import HTMLFormatter, JekyllTurnExporter, MarkdownFormatter
```

It also includes helpers:

```python
from extract_chat.formatters import format_to_markdown
```

Those helpers are lightweight, but the `TurnProcessorV2 -> RenderDocument -> Formatter` flow is the clearest path if you want explicit control.

## Stability Notes

The CLI is the primary public interface.

The Python API is usable today, but it is best treated as a practical integration surface rather than a locked, versioned SDK. If you build against internal processor/formatter classes, expect some evolution over time as schema handling and render models improve.

For that reason:

- prefer `Conversation`, `TurnProcessorV2`, `MarkdownFormatter`, `HTMLFormatter`, and `JekyllTurnExporter`
- avoid depending on underscored methods or test-only helpers
- pin a release tag if you need reproducible behavior in automation

## Related Docs

- `docs/extract_chat.md` for CLI usage
- `docs/extract_chat_architecture.md` for internal pipeline details
- `docs/media-bundle-contract.md` for local media bundle integration

## Navigation

- [Back to README](/Users/mps/projects/AI-PROJECTS/extract-chat/README.md)
- [CLI Guide](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/extract_chat.md)
- [Architecture Guide](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/extract_chat_architecture.md)
- [Media Bundle Contract](/Users/mps/projects/AI-PROJECTS/extract-chat/docs/media-bundle-contract.md)
