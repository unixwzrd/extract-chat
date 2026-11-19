"""HTML formatter for typed conversation render documents."""

from __future__ import annotations

from html import escape
from pathlib import Path
import re
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from extract_chat.css_manager import create_inline_css_style, get_css_content
from extract_chat.formatters.base import BaseFormatter, FormattingError
from extract_chat.formatters.activity_details import JSON_DISPLAY_LABELS, render_activity_details, render_context_citations, render_image_generation
from extract_chat.formatters.turn_index import render_turn_index, turn_anchors
from extract_chat.formatters.display_links import clean_html_links, partition_media_items, render_related_links, render_unavailable_artifact
from extract_chat.processors.reference_processing.reference_utils import (
    build_reference_payload,
    format_apa_reference_entry,
    replace_inline_citation_markers,
)
from extract_chat.schemas.render_models import (
    MediaItem,
    RenderDocument,
    RenderTurn,
    ToolActivityItem,
)

_CITATION_TAG = re.compile(r'(?:<sup id="ref-source-[\w-]+">|<a (?:id="ref-source-[\w-]+"|href="#ref-target-[\w-]+")>|</(?:a|sup)>)')
_CITATION_BLOCK = re.compile(rf"(?:{_CITATION_TAG.pattern}|\[\d+\]|[\s,])+\Z")


def _citation_html(tokens: list[Token], index: int, options: Any, env: Any) -> str:
    """Allow generated citation tags, not executable HTML from a transcript."""
    content = tokens[index].content
    return content if _CITATION_TAG.fullmatch(content) else escape(content)


def _raw_html_block(tokens: list[Token], index: int, options: Any, env: Any) -> str:
    content = tokens[index].content
    return content if _CITATION_BLOCK.fullmatch(content) else f"<pre><code>{escape(content)}</code></pre>\n"


class HTMLFormatter(BaseFormatter):
    """Render conversation logs to standalone HTML."""

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.css_file = self.config.get("css_file")
        self._markdown = MarkdownIt("commonmark", {"html": True}).enable("table")
        self._markdown.renderer.rules["html_inline"] = _citation_html
        self._markdown.renderer.rules["html_block"] = _raw_html_block

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
            if self.config.get("turn_index"):
                parts.append(render_turn_index(document.turns, self._format_timestamp, html=True))

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
            return self._normalize_text(clean_html_links("\n".join(parts), open_new_tabs=True))
        except Exception as exc:
            raise FormattingError(
                f"Failed to format conversation: {exc}", self
            ) from exc

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
            lines.append(
                f"<p><strong>Conversation ID:</strong> {escape(metadata['conversation_id'])}</p>"
            )
        if metadata.get("create_time"):
            lines.append(
                f"<p><strong>Created:</strong> {escape(self._format_timestamp(metadata['create_time']))}</p>"
            )
        if metadata.get("update_time"):
            lines.append(
                f"<p><strong>Last Update:</strong> {escape(self._format_timestamp(metadata['update_time']))}</p>"
            )
        if metadata.get("default_model_slug"):
            lines.append(
                f"<p><strong>Default Model:</strong> {escape(metadata['default_model_slug'])}</p>"
            )
        if any(turn.tools_used for turn in document.turns):
            label = JSON_DISPLAY_LABELS[self.config.get("tool_json", "readable")]
            lines.append(f"<p><strong>Tool JSON:</strong> {escape(label)}</p>")
        lines.append("</div>")
        return lines

    def _render_turn(self, turn: RenderTurn) -> str:
        parts = [f'<article class="block {escape(turn.role)}-block">', turn_anchors(turn)]
        parts.append(f"<h3>{'Exported activity' if turn.metadata.get('activity_only') else turn.role.title()}</h3>")
        parts.append(f'<p class="turn-metadata">Turn: <code style="overflow-wrap:anywhere">{escape(turn.turn_id)}</code><br>Time: {escape(self._format_timestamp(turn.timestamp)) if turn.timestamp is not None else "Not provided"}</p>')
        if turn.role == "assistant" and turn.metadata.get("model_slug"):
            parts.append(f'<p class="turn-metadata"><strong>Model:</strong> {escape(str(turn.metadata["model_slug"]))}</p>')
        if turn.metadata.get("context_citations"):
            parts.append(render_context_citations(turn.metadata["context_citations"], html=True))

        if turn.role == "assistant" and turn.tools_used:
            parts.append(self._render_tools_used(turn.tools_used))

        content = turn.content or ""
        if turn.role == "assistant" and turn.references_table:
            refs = turn.references_table.get("references", [])
            if refs:
                content = replace_inline_citation_markers(content, refs)
        if content.strip():
            parts.append(
                f'<div class="content">{self._convert_markdown_to_html(content)}</div>'
            )

        if turn.role == "assistant" and turn.references_table:
            refs_html = self._render_reference_details(turn)
            if refs_html:
                parts.append(refs_html)

        artifacts, links = partition_media_items(turn.media_items, turn.references_table)
        if artifacts:
            parts.append(self._render_media(artifacts))
        if links:
            parts.append(render_related_links(links))

        parts.append("</article>")
        return "\n".join(parts)

    def _render_tools_used(self, tools: list[ToolActivityItem]) -> str:
        return render_activity_details(tools, html=True, json_mode=self.config.get("tool_json", "readable"), format_time=self._format_timestamp, render_text=self._convert_markdown_to_html)

    def _render_media(self, media_items: list[MediaItem]) -> str:
        parts = [
            '<details class="media-items">',
            "<summary>Artifacts</summary>",
            '<div class="artifact-list">',
        ]
        for item in media_items:
            if item.metadata.get("unavailable_reason"):
                parts.append(render_unavailable_artifact(item))
                continue
            label = escape(item.label)
            kind = escape(item.kind)
            local_path = item.metadata.get("local_path")
            original_url = item.metadata.get("original_url")
            canonical_id = item.metadata.get("canonical_id")
            mime_type = str(item.metadata.get("mime_type") or "").lower()
            suffix = Path(item.url or "").suffix.lower()
            table_rows = item.metadata.get("table_rows")
            if item.url and local_path:
                href = escape(item.url, quote=True)
                body = f'<p><strong>{kind}</strong>: <a href="{href}" download>{label}</a></p>'
                if isinstance(table_rows, list) and table_rows:
                    body += self._render_artifact_table(table_rows)
                elif mime_type.startswith("image/") or suffix in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp",
                    ".avif",
                    ".svg",
                }:
                    body += f'<figure><a href="{href}"><img src="{href}" alt="{label}" loading="lazy" style="max-width:100%;height:auto"></a></figure>'
                elif mime_type.startswith("audio/") or suffix in {
                    ".mp3",
                    ".wav",
                    ".m4a",
                    ".aac",
                    ".flac",
                    ".ogg",
                }:
                    body += f'<audio controls preload="metadata" src="{href}"></audio>'
                elif mime_type.startswith("video/") or suffix in {
                    ".mp4",
                    ".mov",
                    ".webm",
                }:
                    body += f'<video controls preload="metadata" src="{href}" style="max-width:100%"></video>'
                if canonical_id:
                    body += f"<p>File ID: <code>{escape(str(canonical_id))}</code></p>"
                if item.metadata.get("image_generation"):
                    body += render_image_generation(item.metadata["image_generation"], html=True)
                if original_url:
                    body += f'<p><span class="muted">Remote:</span> <code>{escape(str(original_url))}</code></p>'
                parts.append(f'<section class="artifact">{body}</section>')
            elif item.url:
                parts.append(
                    f'<p><strong>{kind}</strong>: <a href="{escape(item.url)}">{label}</a></p>'
                )
            else:
                parts.append(f"<p><strong>{kind}</strong>: <code>{label}</code></p>")
            if not local_path and item.metadata.get("image_generation"):
                parts.append(render_image_generation(item.metadata["image_generation"], html=True))
        parts.extend(["</div>", "</details>"])
        return "\n".join(parts)

    def _render_artifact_table(self, rows: list[list[str]]) -> str:
        if not rows:
            return ""
        width = max(len(row) for row in rows)
        padded = [list(row) + [""] * (width - len(row)) for row in rows]
        head = "".join(f"<th>{escape(str(value))}</th>" for value in padded[0])
        body = "".join(
            "<tr>"
            + "".join(f"<td>{escape(str(value))}</td>" for value in row)
            + "</tr>"
            for row in padded[1:]
        )
        return f'<div class="table-wrapper"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

    def _render_reference_details(self, turn: RenderTurn) -> str:
        payload = build_reference_payload(
            [
                {
                    "type": "assistant",
                    "references_table": turn.references_table or {},
                    "metadata": {
                        "reference_turn_number": turn.metadata.get(
                            "reference_turn_number"
                        )
                    },
                }
            ]
        )
        groups = payload.get("groups", [])
        if not groups:
            return ""

        parts = [
            '<details class="references">',
            "<summary>References</summary>",
            "<ol>",
        ]
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
            snippets = (
                f' <span class="excerpt">"{escape(text)}"</span>'
                if text and not meta.get("is_fallback")
                else ""
            )
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
        parts = [
            '<div class="block system-block">',
            '<div class="block-header">References</div>',
            "<ol>",
        ]
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
        return self._markdown.render(text)
