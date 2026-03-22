"""HTML formatter for typed conversation render documents."""

from __future__ import annotations

from html import escape
from typing import Any

try:
    import markdown as _markdown_lib
except ImportError:  # pragma: no cover
    _markdown_lib = None

from extract_chat.css_manager import create_inline_css_style, get_css_content
from extract_chat.formatters.base import BaseFormatter, FormattingError
from extract_chat.processors.reference_processing.reference_utils import (
    build_reference_payload,
    format_apa_reference_entry,
    replace_inline_citation_markers,
    strip_sources_and_references,
)
from extract_chat.schemas.render_models import MediaItem, RenderDocument, RenderTurn, ToolActivityItem


class HTMLFormatter(BaseFormatter):
    """Render conversation logs to standalone HTML."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.css_file = self.config.get("css_file")

    def get_file_extension(self) -> str:
        return ".html"

    def get_mime_type(self) -> str:
        return "text/html"

    def format_document(self, document: Any) -> str:
        return self.format_conversation(document)

    def format_conversation(self, conversation: Any) -> str:
        try:
            document = self._coerce_document(conversation)
            parts = [
                "<!DOCTYPE html>",
                '<html lang="en">',
                "<head>",
                '    <meta charset="UTF-8">',
                '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
                f"    <title>{escape(document.title or 'Chat Conversation')}</title>",
                create_inline_css_style(get_css_content(self.css_file)),
                "</head>",
                "<body>",
                '<div class="container">',
            ]

            if document.title:
                parts.append(f'<h1 class="title">{escape(document.title)}</h1>')
            parts.extend(self._render_metadata(document))

            if document.system_context:
                parts.append('<section class="system-context">')
                parts.append("<h2>System Context</h2>")
                for entry in document.system_context:
                    parts.append(f"<h3>{escape(entry.title)}</h3>")
                    parts.append(self._wrap_content(entry.content))
                parts.append("</section>")

            parts.append('<section class="conversation">')
            parts.append("<h2>Conversation</h2>")
            for turn in document.turns:
                parts.append(self._render_turn(turn))
            parts.append("</section>")
            parts.append("</div></body></html>")
            return self._normalize_text("\n".join(parts))
        except Exception as exc:
            raise FormattingError(f"Failed to format conversation: {exc}", self) from exc

    def _coerce_document(self, conversation: Any) -> RenderDocument:
        if isinstance(conversation, RenderDocument):
            return conversation
        if isinstance(conversation, dict) and "content_blocks" in conversation:
            return RenderDocument()
        if hasattr(conversation, "model_dump"):
            return RenderDocument.model_validate(conversation.model_dump())
        return RenderDocument.model_validate(conversation)

    def _render_metadata(self, document: RenderDocument) -> list[str]:
        metadata = document.get_metadata()
        lines = ['<div class="metadata">']
        if metadata.get("conversation_id"):
            lines.append(f"<p><strong>Conversation ID:</strong> {escape(metadata['conversation_id'])}</p>")
        if metadata.get("create_time"):
            lines.append(f"<p><strong>Created:</strong> {escape(self._format_timestamp(metadata['create_time']))}</p>")
        if metadata.get("update_time"):
            lines.append(f"<p><strong>Last Update:</strong> {escape(self._format_timestamp(metadata['update_time']))}</p>")
        if metadata.get("default_model_slug"):
            lines.append(f"<p><strong>Default Model:</strong> {escape(metadata['default_model_slug'])}</p>")
        lines.append("</div>")
        return lines

    def _render_turn(self, turn: RenderTurn) -> str:
        parts = [f'<article class="block {escape(turn.role)}-block">']
        header = f"{turn.role.title()} [Turn: {turn.turn_id}]"
        if turn.timestamp:
            header = f"{header} ({self._format_timestamp(turn.timestamp)})"
        parts.append(f"<h3>{escape(header)}</h3>")

        if turn.role == "assistant" and turn.tools_used:
            parts.append(self._render_tools_used(turn.tools_used))

        content = turn.content or ""
        if turn.role == "assistant" and turn.references_table:
            refs = turn.references_table.get("references", [])
            if refs:
                content = replace_inline_citation_markers(content, refs)
        content, _sources = strip_sources_and_references(content)
        if content.strip():
            parts.append(f'<div class="content">{self._convert_markdown_to_html(content)}</div>')

        if turn.media_items:
            parts.append(self._render_media(turn.media_items))

        if turn.role == "assistant" and turn.references_table:
            refs_html = self._render_reference_details(turn)
            if refs_html:
                parts.append(refs_html)

        parts.append("</article>")
        return "\n".join(parts)

    def _render_tools_used(self, tools: list[ToolActivityItem]) -> str:
        parts = ["<details class=\"tools-used\">", "<summary>Tools Used</summary>"]
        for item in tools:
            parts.append('<div class="tool-item">')
            parts.append(f"<strong>{escape(item.title)}</strong>")
            meta_bits: list[str] = []
            if item.timestamp:
                meta_bits.append(self._format_timestamp(item.timestamp))
            if item.content_type:
                meta_bits.append(item.content_type)
            if item.turn_id:
                meta_bits.append(f"Turn: {item.turn_id}")
            model_slug = item.metadata.get("model_slug")
            if model_slug:
                meta_bits.append(f"Model: {model_slug}")
            if meta_bits:
                parts.append(f"<p><em>{escape(' | '.join(meta_bits))}</em></p>")
            if item.content:
                if item.language:
                    parts.append(
                        f'<pre><code class="language-{escape(item.language)}">{escape(item.content)}</code></pre>'
                    )
                else:
                    parts.append(self._wrap_content(item.content))
            search_queries = item.metadata.get("search_queries") or []
            if search_queries:
                parts.append("<p><strong>Search Queries</strong></p><ul>")
                for query in search_queries:
                    query_text = query.get("q") if isinstance(query, dict) else str(query)
                    if query_text:
                        parts.append(f"<li>{escape(query_text)}</li>")
                parts.append("</ul>")
            parts.append("</div>")
        parts.append("</details>")
        return "\n".join(parts)

    def _render_media(self, media_items: list[MediaItem]) -> str:
        parts = ['<details class="media-items">', "<summary>Media</summary>", "<ul>"]
        for item in media_items:
            label = escape(item.label)
            kind = escape(item.kind)
            local_path = item.metadata.get("local_path")
            original_url = item.metadata.get("original_url")
            canonical_id = item.metadata.get("canonical_id")
            if item.url and local_path:
                body = f'<strong>{kind}</strong>: <a href="{escape(item.url)}">{label}</a>'
                if canonical_id:
                    body = f'{body} <code>{escape(str(canonical_id))}</code>'
                if original_url:
                    body = f'{body} <span class="muted">remote:</span> <code>{escape(str(original_url))}</code>'
                parts.append(f"<li>{body}</li>")
            elif item.url:
                parts.append(f'<li><strong>{kind}</strong>: <a href="{escape(item.url)}">{label}</a></li>')
            else:
                parts.append(f"<li><strong>{kind}</strong>: <code>{label}</code></li>")
        parts.extend(["</ul>", "</details>"])
        return "\n".join(parts)

    def _render_reference_details(self, turn: RenderTurn) -> str:
        payload = build_reference_payload(
            [
                {
                    "type": "assistant",
                    "references_table": turn.references_table or {},
                    "metadata": {"reference_turn_number": turn.metadata.get("reference_turn_number")},
                }
            ]
        )
        groups = payload.get("groups", [])
        if not groups:
            return ""

        parts = ['<details class="references">', "<summary>References</summary>", "<ol>"]
        for index, group in enumerate(groups, start=1):
            meta = group.get("meta") or {}
            occurrences = group.get("occurrences") or []
            anchors = "".join(
                f'<a id="ref-target-{occ.get("unique_id")}"></a>'
                for occ in occurrences
                if occ.get("unique_id")
            )
            seq = meta.get("seq") or index
            citation = format_apa_reference_entry(meta, html=True)
            text = (meta.get("text") or "").strip().replace("\n", " ")
            snippets = f' <span class="excerpt">"{escape(text)}"</span>' if text and not meta.get("is_fallback") else ""
            backlinks = [
                f'<a class="backref" href="#ref-source-{occ.get("unique_id")}">{escape(occ.get("backlink_label"))}^</a>'
                for occ in occurrences
                if occ.get("unique_id") and occ.get("backlink_label")
            ]
            body = f"<strong>Ref {seq}.</strong> {citation}{snippets}"
            if backlinks:
                body = f"{body} {' , '.join(backlinks)}"
            parts.append(f"<li>{anchors}{body}</li>")
        parts.extend(["</ol>", "</details>"])
        return "\n".join(parts)

    def _generate_global_references_section_html(
        self,
        content_blocks: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        payload = build_reference_payload(content_blocks)
        groups = payload.get("groups", [])
        if not groups:
            return "", []
        parts = ['<div class="block system-block">', '<div class="block-header">References</div>', "<ol>"]
        for index, group in enumerate(groups, start=1):
            meta = group.get("meta") or {}
            occurrences = group.get("occurrences") or []
            anchors = "".join(
                f'<a id="ref-target-{occ.get("unique_id")}"></a>'
                for occ in occurrences
                if occ.get("unique_id")
            )
            seq = meta.get("seq") or index
            citation = format_apa_reference_entry(meta, html=True)
            backlinks = [
                f'<a class="backref" href="#ref-source-{occ.get("unique_id")}">{escape(occ.get("backlink_label"))}^</a>'
                for occ in occurrences
                if occ.get("unique_id") and occ.get("backlink_label")
            ]
            body = f"<strong>Ref {seq}.</strong> {citation}"
            if backlinks:
                body = f"{body} {' , '.join(backlinks)}"
            parts.append(f"<li>{anchors}{body}</li>")
        parts.extend(["</ol>", "</div>"])
        return "\n".join(parts), groups

    def _wrap_content(self, text: str) -> str:
        return f'<div class="content">{self._convert_markdown_to_html(text)}</div>'

    def _convert_markdown_to_html(self, text: str) -> str:
        if not text:
            return ""
        if _markdown_lib:
            try:
                return _markdown_lib.markdown(text, extensions=["tables", "fenced_code"])
            except Exception:
                pass
        paragraphs = []
        for block in text.split("\n\n"):
            stripped = block.strip()
            if not stripped:
                continue
            paragraphs.append(f"<p>{escape(stripped)}</p>")
        return "\n".join(paragraphs)
