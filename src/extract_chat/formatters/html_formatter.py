"""
HTML formatter for extract_chat_v2.

This module implements the formatter that converts ChatGPT conversations
to HTML format with proper styling and structure.
"""

from typing import Any, Dict, List, Optional

# ftfy import moved to base class
from pylib.css_manager import create_inline_css_style, get_css_content
from pylib.schemas import Conversation

from .base import BaseFormatter, FormattingError


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

    def format_conversation(self, conversation: Conversation) -> str:
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

            # Close container and body
            html_parts.append('</div>')
            html_parts.append('</body>')
            html_parts.append('</html>')

            # Apply final Unicode normalization to the entire output
            html_content = '\n'.join(html_parts)
            return self._normalize_text(html_content)

        except Exception as e:
            raise FormattingError(f"Failed to format conversation: {str(e)}", self)

    def format_document(self, conversation: Conversation) -> str:
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
                create_date = metadata['create_time'].strftime('%Y-%m-%d %H:%M:%S')
                lines.append(f'<p><strong>Created:</strong> {create_date}</p>')
            
            if metadata.get('update_time'):
                update_date = metadata['update_time'].strftime('%Y-%m-%d %H:%M:%S')
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
        role = block.get('role', 'unknown')
        content = block.get('content', '')
        timestamp = block.get('timestamp')
        
        # Determine CSS class based on role
        css_class = f"{role.lower()}-block"
        
        html_parts = [f'<div class="block {css_class}">']
        
        # Add header with role and timestamp
        block_id = block.get('block_id', 'unknown')
        if timestamp:
            header_parts = [f'<h3>{role.title()} ({timestamp.strftime("%Y-%m-%d %H:%M:%S")}) [Turn: {block_id}]</h3>']
        else:
            header_parts = [f'<h3>{role.title()} [Turn: {block_id}]</h3>']
        
        html_parts.append(''.join(header_parts))
        
        # Add content with markdown conversion
        converted_content = self._convert_markdown_to_html(content)
        # Clean up extra whitespace and newlines
        converted_content = self._clean_html_content(converted_content)
        html_parts.append(f'<div class="content">{converted_content}</div>')
        
        # Add citations if present
        citations = block.get('citations', [])
        if citations:
            html_parts.append(self._format_citations_html(citations))
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)

    def _format_code_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a code block dictionary to HTML."""
        role = block.get('role', 'unknown')
        content = block.get('content', '')
        language = block.get('language', '')
        timestamp = block.get('timestamp')
        
        # Content is already normalized at the schema level
        
        css_class = f"{role.lower()}-block"
        
        html_parts = [f'<div class="block {css_class}">']
        
        # Add header
        block_id = block.get('block_id', 'unknown')
        if timestamp:
            header_parts = [f'<h3>{role.title()} - Code ({timestamp.strftime("%Y-%m-%d %H:%M:%S")}) [Turn: {block_id}]</h3>']
        else:
            header_parts = [f'<h3>{role.title()} - Code [Turn: {block_id}]</h3>']
        
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
        timestamp = block.get('timestamp')
        
        css_class = f"{role.lower()}-block"
        
        html_parts = [f'<div class="block {css_class}">']
        
        # Add header
        block_id = block.get('block_id', 'unknown')
        if timestamp:
            header_parts = [f'<h3>Tool Call: {tool_name} ({self._format_timestamp(timestamp)}) [Turn: {block_id}]</h3>']
        else:
            header_parts = [f'<h3>Tool Call: {tool_name} [Turn: {block_id}]</h3>']
        
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
        
        # If text already contains HTML tags (like <pre><code>), don't process it further
        if '<pre>' in text or '<code>' in text:
            return text
        
        # Convert unordered lists
        lines = text.split('\n')
        html_lines = []
        in_list = False
        current_paragraph = []
        
        for line in lines:
            stripped = line.strip()
            
            # Handle unordered list items
            if stripped.startswith('- ') or stripped.startswith('* '):
                # Close any open paragraph
                if current_paragraph:
                    html_lines.append(f'<p>{" ".join(current_paragraph)}</p>')
                    current_paragraph = []
                
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{stripped[2:]}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                
                # Add to current paragraph (don't create new paragraph for every line)
                if stripped:
                    current_paragraph.append(stripped)
                elif current_paragraph:
                    # Empty line ends current paragraph
                    html_lines.append(f'<p>{" ".join(current_paragraph)}</p>')
                    current_paragraph = []
        
        # Close any open paragraph
        if current_paragraph:
            html_lines.append(f'<p>{" ".join(current_paragraph)}</p>')
        
        # Close any open list
        if in_list:
            html_lines.append('</ul>')
        
        return '\n'.join(html_lines)
