"""HTML formatter for extract_chat_v2."""

import re
from html import escape
from typing import Any, Dict, List, Optional

try:
    import markdown as _markdown_lib
except ImportError:  # pragma: no cover - optional dependency
    _markdown_lib = None


def _ensure_trailing_period(value: str) -> str:
    text = value.strip()
    if not text:
        return ''
    return text if text.endswith('.') else f"{text}."


def _normalize_reference_text(value: str) -> str:
    text = value.lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return text.strip()

# ftfy import moved to base class
from extract_chat.css_manager import create_inline_css_style, get_css_content
from extract_chat.formatters.base import BaseFormatter, FormattingError
from extract_chat.formatters.reference_utils import (
    extract_reference_groups,
    format_apa_reference_entry,
    generate_backlink_labels,
    replace_inline_citation_markers,
)


class HTMLFormatter(BaseFormatter):
    """
    Formatter for HTML output.

    This formatter converts ChatGPT conversations to HTML format
    with embedded CSS styling for a clean, readable presentation.
    """

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self.css_file = config.get('css_file') if config else None

    def get_file_extension(self) -> str:
        return ".html"

    def get_mime_type(self) -> str:
        return "text/html"

    def _format_timestamp(self, timestamp):
        """Format timestamp for display (accepts epoch floats)."""
        if timestamp is None:
            return ""
        try:
            from datetime import datetime
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            try:
                return str(timestamp)
            except Exception:
                return ""

    def format_conversation(self, conversation: Any) -> str:
        """
        Format a conversation to HTML.

        Args:
            conversation: The ChatGPT conversation object

        Returns:
            Formatted HTML string
        """
        try:
            # Validate conversation
            if not self.validate_document(conversation):
                raise FormattingError("Conversation validation failed")

            # Build HTML content
            html_parts = []

            # Get metadata
            metadata = conversation.get_metadata()
            title = metadata.get('title', 'ChatGPT Conversation')

            # Add HTML header
            html_parts.append(self._get_html_header(title))

            # Add CSS styles
            css_content = get_css_content(self.css_file)
            html_parts.append(create_inline_css_style(css_content))

            # Add body start
            html_parts.append('<body>')

            # Add container
            html_parts.append('<div class="container">')

            # Add title
            html_parts.append(f'<h1 class="title">{title}</h1>')

            # Add metadata
            html_parts.extend(self._format_metadata_html(metadata))

            # Add content blocks
            content_blocks = conversation.get_content_blocks()
            for block in content_blocks:
                block_html = self._format_block_dict(block)
                if block_html:
                    html_parts.append(block_html)

            # Append a global References section (HTML) aggregating across assistant blocks
            refs_html, reference_groups = self._generate_global_references_section_html(content_blocks)
            rendered_sources = ''
            if reference_groups:
                sources_html = self._render_sources_list_html(reference_groups)
                rendered_sources = (
                    '<strong>Sources:</strong>\n'
                    '<ul class="sources">\n'
                    f'{sources_html}\n'
                    '</ul>\n\n'
                )
            if refs_html:
                html_parts.append(refs_html)

            # Close container and body
            html_parts.append('</div>')
            html_parts.append('</body>')
            html_parts.append('</html>')

            # Apply final Unicode normalization to the entire output
            html_content = '\n'.join(html_parts)
            html_content = self._normalize_text(html_content)
            if reference_groups:
                html_content = re.sub(
                    r'<strong>Sources:</strong>.*?(?=<div class="block system-block">)',
                    rendered_sources,
                    html_content,
                    flags=re.S,
                )
            return html_content

        except Exception as e:
            raise FormattingError(f"Failed to format conversation: {str(e)}", self)

    def format_document(self, conversation: Any) -> str:
        """Wrapper for compatibility with BaseFormatter."""
        return self.format_conversation(conversation)

    def _get_html_header(self, title: str) -> str:
        """Get the HTML document header."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>'''

    def _get_css_styles(self) -> str:
        """Get the CSS styles for the document."""
        # This method is now deprecated - CSS is handled by css_manager
        css_content = get_css_content(self.css_file)
        return create_inline_css_style(css_content)

    def _format_metadata_html(self, metadata: Dict[str, Any]) -> List[str]:
        """Format conversation metadata to HTML."""
        lines = []
        
        if metadata.get('create_time') or metadata.get('update_time') or metadata.get('model'):
            lines.append('<div class="metadata">')
            
            if metadata.get('create_time'):
                create_date = self._format_timestamp(metadata['create_time'])
                lines.append(f'<p><strong>Created:</strong> {create_date}</p>')
            
            if metadata.get('update_time'):
                update_date = self._format_timestamp(metadata['update_time'])
                lines.append(f'<p><strong>Updated:</strong> {update_date}</p>')
            
            if metadata.get('model'):
                lines.append(f'<p><strong>Model:</strong> {metadata["model"]}</p>')
            
            if metadata.get('conversation_id'):
                lines.append(f'<p><strong>Conversation ID:</strong> {metadata["conversation_id"]}</p>')
            
            lines.append('</div>')
        
        return lines

    def _format_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a content block dictionary to HTML."""
        block_type = block.get('block_type', block.get('type', 'text'))
        
        if block_type == 'text':
            return self._format_text_block_dict(block)
        elif block_type == 'code':
            return self._format_code_block_dict(block)
        elif block_type == 'tool_call':
            return self._format_tool_call_block_dict(block)
        elif block_type == 'user_context' or block_type == 'conversation_context':
            return self._format_user_context_block_dict(block)
        else:
            return self._format_text_block_dict(block)  # Default to text

    def _format_text_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a text block dictionary to HTML."""
        role = block.get('role') or block.get('type', 'unknown')
        content = block.get('content', '')
        metadata = block.get('metadata', {}) or {}
        timestamp = metadata.get('timestamp') or block.get('timestamp')
        turn_id = metadata.get('turn_id') or block.get('block_id', 'unknown')

        # Determine CSS class based on role
        css_class = f"{role.lower()}-block"

        html_parts = [f'<div class="block {css_class}">']

        # Add header with role and timestamp
        role_title = (role or 'unknown').title()
        if timestamp:
            header_parts = [
                f'<h3>{role_title} ({self._format_timestamp(timestamp)}) '
                f'[Turn: {escape(str(turn_id))}]</h3>'
            ]
        else:
            header_parts = [f'<h3>{role_title} [Turn: {escape(str(turn_id))}]</h3>']
        
        html_parts.append(''.join(header_parts))
        
        # Add content with markdown conversion
        # Replace inline markers with cite superscripts if we have references
        refs_block = block.get('references_table')
        if content and refs_block and refs_block.get('references'):
            content = replace_inline_citation_markers(content, refs_block.get('references', []))
        converted_content = self._convert_markdown_to_html(content)
        # Clean up extra whitespace and newlines
        converted_content = self._clean_html_content(converted_content)
        if '<strong>Sources:</strong>' in converted_content:
            converted_content = converted_content.split('<strong>Sources:</strong>', 1)[0].rstrip()
        html_parts.append(f'<div class="content">{converted_content}</div>')
        
        # Add citations if present
        citations = block.get('citations', [])
        if citations:
            html_parts.append(self._format_citations_html(citations))
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)

    def _generate_global_references_section_html(
        self,
        content_blocks: List[Dict[str, Any]],
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Aggregate references across assistant blocks and render as an HTML section."""
        try:
            groups = extract_reference_groups(content_blocks)
            if not groups:
                return "", []

            parts: List[str] = [
                '<div class="block system-block">',
                '<div class="block-header">References</div>',
                '<div class="content">',
                '<ol class="references">',
            ]

            for index, group in enumerate(groups, start=1):
                meta = group.get('meta') or {}
                occurrences = group.get('occurrences') or []
                if not occurrences:
                    continue

                anchor_html = ''.join(
                    f'<a id="ref-target-{occ.get("unique_id")}"></a>'
                    for occ in occurrences
                    if occ.get('unique_id')
                )

                seq_values = [int(occ.get('seq', 10**9)) for occ in occurrences if occ.get('seq') is not None]
                seq_values = [s for s in seq_values if s != 10**9]
                label_seq = seq_values[0] if seq_values else index
                citation_label = f"Ref {label_seq}"
                apa_text = format_apa_reference_entry(meta, html=True)
                snippet = ''
                if not meta.get('is_fallback'):
                    snippet = (meta.get('text') or '').strip().replace('\n', ' ')
                snippet_html = f'<span class="excerpt">“{escape(snippet)}”</span>' if snippet else ''

                backlinks: List[str] = []
                default_letters = generate_backlink_labels(len(occurrences))
                for idx, occ in enumerate(occurrences):
                    uid = occ.get('unique_id')
                    if not uid:
                        continue
                    label = (occ.get('occurrence_label') or '').strip() or default_letters[idx]
                    link = f'<a class="backref" href="#ref-source-{uid}">{label}^</a>'
                    backlinks.append(link)

                body_parts = [f'<strong>{escape(citation_label)}.</strong> {apa_text}']
                if snippet_html:
                    body_parts.append(snippet_html)
                if backlinks:
                    body_parts.append(', '.join(backlinks))
                body = ' '.join(part for part in body_parts if part)
                parts.append(f'<li>{anchor_html} {body}</li>')

            parts.append('</ol>')
            parts.append('</div>')
            parts.append('</div>')
            return '\n'.join(parts), groups
        except Exception:
            return "", []

    def _render_sources_list_html(self, reference_groups: List[Dict[str, Any]]) -> str:
        items: List[str] = []
        seen: set[int] = set()
        for group in reference_groups:
            meta = group.get('meta') or {}
            seq = meta.get('seq')
            if not isinstance(seq, int) or seq in seen:
                continue
            seen.add(seq)
            title = (meta.get('title') or '').strip()
            label = (meta.get('source_label') or '').strip()
            url = (meta.get('url') or '').strip()
            display = self._compose_source_display(title, label)
            if url:
                items.append(f'<li>{seq}. <a href="{url}">{escape(display)}</a></li>')
            else:
                items.append(f'<li>{seq}. {escape(display)}</li>')
        return '\n'.join(items)

    @staticmethod
    def _compose_source_display(title: str, label: str) -> str:
        if label and not title:
            return label
        if not label and title:
            return title
        if not label and not title:
            return "Reference"

        norm_title = _normalize_reference_text(title)
        norm_label = _normalize_reference_text(label)
        if norm_title and norm_label and (norm_title in norm_label or norm_label in norm_title):
            return label
        if norm_title:
            return title
        return label

    def _format_code_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a code block dictionary to HTML."""
        role = block.get('role') or block.get('type', 'unknown')
        content = block.get('content', '')
        language = block.get('language', '')
        metadata = block.get('metadata', {}) or {}
        timestamp = metadata.get('timestamp') or block.get('timestamp')

        # Content is already normalized at the schema level

        css_class = f"{role.lower()}-block"

        html_parts = [f'<div class="block {css_class}">']

        # Add header
        turn_id = metadata.get('turn_id') or block.get('block_id', 'unknown')
        role_title = (role or 'unknown').title()
        if timestamp:
            header_parts = [
                f'<h3>{role_title} - Code ({self._format_timestamp(timestamp)}) '
                f'[Turn: {escape(str(turn_id))}]</h3>'
            ]
        else:
            header_parts = [f'<h3>{role_title} - Code [Turn: {escape(str(turn_id))}]</h3>']
        
        if language:
            header_parts[0] = header_parts[0].replace('</h3>', f' ({language})</h3>')
        
        html_parts.append(''.join(header_parts))
        
        # Add code content
        html_parts.append(f'<div class="code-block">{content}</div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)

    def _format_tool_call_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a tool call block dictionary to HTML."""
        role = block.get('role', 'tool')
        tool_name = block.get('tool_name', 'unknown_tool')
        tool_input = block.get('tool_input', {})
        tool_output = block.get('tool_output', {})
        metadata = block.get('metadata', {}) or {}
        timestamp = metadata.get('timestamp') or block.get('timestamp')

        css_class = f"{role.lower()}-block"

        html_parts = [f'<div class="block {css_class}">']

        # Add header
        turn_id = metadata.get('turn_id') or block.get('block_id', 'unknown')
        if timestamp:
            header_parts = [
                f'<h3>Tool Call: {escape(str(tool_name))} '
                f'({self._format_timestamp(timestamp)}) [Turn: {escape(str(turn_id))}]</h3>'
            ]
        else:
            header_parts = [f'<h3>Tool Call: {escape(str(tool_name))} [Turn: {escape(str(turn_id))}]</h3>']
        
        html_parts.append(''.join(header_parts))
        
        # Add tool call details
        html_parts.append('<div class="tool-call">')
        
        if tool_input:
            html_parts.append('<div class="tool-input">')
            html_parts.append('<strong>Input:</strong>')
            html_parts.append(f'<pre>{str(tool_input)}</pre>')
            html_parts.append('</div>')
        
        if tool_output:
            html_parts.append('<div class="tool-output">')
            html_parts.append('<strong>Output:</strong>')
            html_parts.append(f'<pre>{str(tool_output)}</pre>')
            html_parts.append('</div>')
        
        html_parts.append('</div>')
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)

    def _format_user_context_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a user context block dictionary to HTML."""
        # Extract context data using shared method (same as markdown formatter)
        context_data = self._extract_conversation_context_data(block)
        user_profile = context_data['user_profile']
        user_instructions = context_data['user_instructions']
        about_user = context_data['about_user']
        about_model = context_data['about_model']
        
        html_parts = []
        
        # Add User Profile section
        if user_profile:
            html_parts.append('<div class="block system-block">')
            html_parts.append('<div class="block-header">User Profile</div>')
            html_parts.append('<div class="content">')
            # Convert markdown to HTML
            converted_profile = self._convert_markdown_to_html(user_profile)
            fixed_profile = self._convert_triple_backticks_to_html(converted_profile)
            html_parts.append(fixed_profile)
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        # Add User Instructions section
        if user_instructions:
            html_parts.append('<div class="block system-block">')
            html_parts.append('<div class="block-header">User Instructions</div>')
            html_parts.append('<div class="content">')
            # Convert markdown to HTML
            converted_instructions = self._convert_markdown_to_html(user_instructions)
            fixed_instructions = self._convert_triple_backticks_to_html(converted_instructions)
            html_parts.append(fixed_instructions)
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        # Add About The User section
        if about_user:
            html_parts.append('<div class="block system-block">')
            html_parts.append('<div class="block-header">About The User</div>')
            html_parts.append('<div class="content">')
            # Convert markdown to HTML
            converted_about_user = self._convert_markdown_to_html(about_user)
            html_parts.append(converted_about_user)
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        # Add About The Model section
        if about_model:
            html_parts.append('<div class="block system-block">')
            html_parts.append('<div class="block-header">About The Model</div>')
            html_parts.append('<div class="content">')
            # Convert markdown to HTML
            converted_about_model = self._convert_markdown_to_html(about_model)
            html_parts.append(converted_about_model)
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        return '\n'.join(html_parts)

    def _format_citations_html(self, citations: List[Dict[str, Any]]) -> str:
        """Format citations to HTML."""
        if not citations:
            return ""
        
        html_parts = ['<div class="citations">']
        for citation in citations:
            title = citation.get('title', 'Unknown Source')
            url = citation.get('url', '')
            
            html_parts.append('<div class="citation">')
            if url:
                html_parts.append(f'<a href="{url}" class="reference-url" target="_blank">{title}</a>')
            else:
                html_parts.append(title)
            html_parts.append('</div>')
        
        html_parts.append('</div>')
        return '\n'.join(html_parts)

    # Use shared _normalize_text from base class

    def _clean_html_content(self, content: str) -> str:
        """
        Clean up HTML content by removing excessive whitespace and newlines.
        
        Args:
            content: HTML content to clean
            
        Returns:
            Cleaned HTML content
        """
        if not content:
            return ""
        
        # Remove excessive newlines and whitespace
        import re

        # Replace multiple newlines with single newlines
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        # Remove leading/trailing whitespace from each line
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
            elif cleaned_lines and cleaned_lines[-1]:  # Keep one empty line between content
                cleaned_lines.append("")
        
        # Remove trailing empty lines
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)

    def _convert_triple_backticks_to_html(self, text: str) -> str:
        """
        Convert triple backticks to HTML pre/code blocks.
        
        Args:
            text: Text containing triple backticks
            
        Returns:
            Text with triple backticks converted to HTML
        """
        if '```' not in text:
            return text
        
        # Split by triple backticks to process each occurrence
        parts = text.split('```')
        result_parts = []
        
        for i, part in enumerate(parts):
            if i == 0:
                # First part (before any backticks)
                result_parts.append(part)
                continue
            
            if i % 2 == 1:
                # This is content inside backticks (odd indices)
                # Convert to HTML pre/code block with language class
                result_parts.append(f'<pre><code class="language-text">{part}</code></pre>')
            else:
                # This is content between backtick blocks (even indices)
                result_parts.append(part)
        
        return ''.join(result_parts)

    def _convert_markdown_to_html(self, text: str) -> str:
        """
        Convert basic markdown elements to HTML.
        
        Args:
            text: Text containing markdown elements
            
        Returns:
            Text with markdown converted to HTML
        """
        if not text:
            return ""

        if '<pre>' in text or '<code>' in text:
            return text

        if _markdown_lib:
            try:
                return _markdown_lib.markdown(text, extensions=['tables', 'fenced_code', 'toc'])
            except Exception:  # pragma: no cover - fallback below
                pass

        # Basic fallback for headings and paragraphs if markdown library not available
        lines = text.split('\n')
        html_lines: List[str] = []
        in_list = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('')
                continue

            if stripped.startswith('#'):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                level = len(stripped) - len(stripped.lstrip('#'))
                level = max(1, min(level, 6))
                content = stripped[level:].strip()
                html_lines.append(f'<h{level}>{escape(content)}</h{level}>')
            elif stripped.startswith(('- ', '* ')):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{escape(stripped[2:].strip())}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<p>{escape(stripped)}</p>')

        if in_list:
            html_lines.append('</ul>')

        return '\n'.join(filter(None, html_lines))
