"""
Rich metadata formatting functions for ChatGPT JSON exports.

This module contains specialized formatters for handling rich metadata structures
discovered in ChatGPT JSON exports, including:
- Search result groups
- Content references
- Tool-specific metadata
- Special content types

Each formatter provides both Markdown and HTML output options.
"""

from schemas import Message


def format_special_content_types(message: Message, html: bool = False) -> str:
    """
    Format special content types that don't follow the standard parts structure.

    Args:
        message: The message to format
        html: If True, return HTML formatting; if False, return Markdown

    Returns:
        Formatted content string
    """
    content = message.content

    # Handle model_editable_context
    if content.content_type == "model_editable_context":
        parts = []
        if content.model_set_context:
            if html:
                parts.append(f"<strong>Model Context:</strong> {content.model_set_context}")
            else:
                parts.append(f"**Model Context:** {content.model_set_context}")
        if content.repository:
            if html:
                parts.append(f"<strong>Repository:</strong> {content.repository}")
            else:
                parts.append(f"**Repository:** {content.repository}")
        if content.repo_summary:
            if html:
                parts.append(f"<strong>Repository Summary:</strong> {content.repo_summary}")
            else:
                parts.append(f"**Repository Summary:** {content.repo_summary}")
        if content.structured_context:
            if html:
                parts.append(f"<strong>Structured Context:</strong> {content.structured_context}")
            else:
                parts.append(f"**Structured Context:** {content.structured_context}")

        if parts:
            return "<br><br>".join(parts) if html else "\n\n".join(parts)
        else:
            return ("<em>Model editable context (no details available)</em>"
                   if html else "*Model editable context (no details available)*")

    # Handle thoughts content
    elif content.content_type == "thoughts":
        parts = []
        if content.source_analysis_msg_id:
            if html:
                parts.append(f"<strong>Analysis Message ID:</strong> {content.source_analysis_msg_id}")
            else:
                parts.append(f"**Analysis Message ID:** {content.source_analysis_msg_id}")
        if content.thoughts:
            if html:
                parts.append(f"<strong>Thoughts:</strong> {content.thoughts}")
            else:
                parts.append(f"**Thoughts:** {content.thoughts}")

        if parts:
            return "<br><br>".join(parts) if html else "\n\n".join(parts)
        else:
            return "<em>Thoughts content (no details available)</em>" if html else "*Thoughts content (no details available)*"

    # Handle tether_browsing_display
    elif content.content_type == "tether_browsing_display":
        parts = []
        if content.tether_id:
            if html:
                parts.append(f"<strong>Tether ID:</strong> {content.tether_id}")
            else:
                parts.append(f"**Tether ID:** {content.tether_id}")
        if content.summary:
            if html:
                parts.append(f"<strong>Summary:</strong> {content.summary}")
            else:
                parts.append(f"**Summary:** {content.summary}")
        if content.result:
            if html:
                parts.append(f"<strong>Result:</strong> {content.result}")
            else:
                parts.append(f"**Result:** {content.result}")
        if content.assets:
            if html:
                parts.append(f"<strong>Assets:</strong> {len(content.assets)} items")
            else:
                parts.append(f"**Assets:** {len(content.assets)} items")

        if parts:
            return "<br><br>".join(parts) if html else "\n\n".join(parts)
        else:
            return "<em>Tether browsing display (no details available)</em>" if html else "*Tether browsing display (no details available)*"

    # Handle user_editable_context
    elif content.content_type == "user_editable_context":
        parts = []
        if content.user_profile:
            if html:
                parts.append(f"<strong>User Profile:</strong> {content.user_profile}")
            else:
                parts.append(f"**User Profile:** {content.user_profile}")
        if content.user_instructions:
            if html:
                parts.append(f"<strong>User Instructions:</strong> {content.user_instructions}")
            else:
                parts.append(f"**User Instructions:** {content.user_instructions}")

        if parts:
            return "<br><br>".join(parts) if html else "\n\n".join(parts)
        else:
            return "<em>User editable context (no details available)</em>" if html else "*User editable context (no details available)*"

    # Default case - return empty string for unknown content types
    else:
        return f"<em>Content type '{content.content_type}' not yet supported</em>" if html else f"*Content type '{content.content_type}' not yet supported*"


def format_search_results(message: Message, html: bool = False) -> str:
    """
    Format search result groups from tool-generated messages.

    Args:
        message: The message containing search results
        html: If True, return HTML formatting; if False, return Markdown

    Returns:
        Formatted search results string
    """
    if not message.metadata or not message.metadata.search_result_groups:
        return ""

    parts = []
    if html:
        parts.append("<strong>Search Results:</strong>")
    else:
        parts.append("**Search Results:**")

    for group in message.metadata.search_result_groups:
        if html:
            parts.append(f"<h3>{group.domain}</h3>")
        else:
            parts.append(f"\n### {group.domain}")

        for entry in group.entries:
            if html:
                parts.append(f"<p><strong>{entry.title}</strong></p>")
            else:
                parts.append(f"\n**{entry.title}**")

            if entry.url:
                if html:
                    parts.append(f"<p>URL: <a href='{entry.url}'>{entry.url}</a></p>")
                else:
                    parts.append(f"URL: {entry.url}")
            if entry.snippet:
                if html:
                    parts.append(f"<p>Snippet: {entry.snippet}</p>")
                else:
                    parts.append(f"Snippet: {entry.snippet}")
            if entry.attribution:
                if html:
                    parts.append(f"<p>Source: {entry.attribution}</p>")
                else:
                    parts.append(f"Source: {entry.attribution}")
            if entry.pub_date:
                if html:
                    parts.append(f"<p>Date: {entry.pub_date}</p>")
                else:
                    parts.append(f"Date: {entry.pub_date}")
            if html:
                parts.append("<br>")  # Empty line between entries
            else:
                parts.append("")  # Empty line between entries

    return "\n".join(parts)


def format_content_references(message: Message, html: bool = False) -> str:
    """
    Format content references from tool-generated messages.

    Args:
        message: The message containing content references
        html: If True, return HTML formatting; if False, return Markdown

    Returns:
        Formatted content references string
    """
    if not message.metadata or not message.metadata.content_references:
        return ""

    parts = []
    if html:
        parts.append("<strong>Content References:</strong>")
    else:
        parts.append("**Content References:**")

    for ref in message.metadata.content_references:
        if ref.type == "grouped_webpages" and ref.items:
            if html:
                parts.append(f"<h3>{ref.matched_text} ({ref.start_idx}-{ref.end_idx})</h3>")
            else:
                parts.append(f"\n### {ref.matched_text} ({ref.start_idx}-{ref.end_idx})")

            for item in ref.items:
                if html:
                    parts.append(f"<p><strong>{item.title}</strong></p>")
                else:
                    parts.append(f"\n**{item.title}**")

                if item.url:
                    if html:
                        parts.append(f"<p>URL: <a href='{item.url}'>{item.url}</a></p>")
                    else:
                        parts.append(f"URL: {item.url}")
                if item.snippet:
                    if html:
                        parts.append(f"<p>Snippet: {item.snippet}</p>")
                    else:
                        parts.append(f"Snippet: {item.snippet}")
                if item.attributions:
                    if html:
                        parts.append(f"<p>Attributions: {item.attributions}</p>")
                    else:
                        parts.append(f"Attributions: {item.attributions}")
                if html:
                    parts.append("<br>")  # Empty line between items
                else:
                    parts.append("")  # Empty line between items

    return "\n".join(parts)


def format_safe_urls(message: Message, html: bool = False) -> str:
    """
    Format safe URLs from tool-generated messages.

    Args:
        message: The message containing safe URLs
        html: If True, return HTML formatting; if False, return Markdown

    Returns:
        Formatted safe URLs string
    """
    if not message.metadata or not message.metadata.safe_urls:
        return ""

    parts = []
    if html:
        parts.append("<strong>Safe URLs:</strong>")
    else:
        parts.append("**Safe URLs:**")

    for url in message.metadata.safe_urls:
        if html:
            parts.append(f"<li><a href='{url}'>{url}</a></li>")
        else:
            parts.append(f"- {url}")

    if html:
        return f"<ul>{''.join(parts)}</ul>"
    else:
        return "\n".join(parts)


def format_tool_metadata(message: Message, html: bool = False) -> str:
    """
    Format tool-specific metadata for display.

    Args:
        message: The message containing tool metadata
        html: If True, return HTML formatting; if False, return Markdown

    Returns:
        Formatted tool metadata string
    """
    if not message.metadata:
        return ""

    parts = []

    # Add real_author if present
    if message.metadata.real_author:
        if html:
            parts.append(f"<strong>Generated by:</strong> {message.metadata.real_author}")
        else:
            parts.append(f"**Generated by:** {message.metadata.real_author}")

    # Add search source info
    if message.metadata.search_source:
        if html:
            parts.append(f"<strong>Search Source:</strong> {message.metadata.search_source}")
        else:
            parts.append(f"**Search Source:** {message.metadata.search_source}")

    # Add command info
    if message.metadata.command:
        if html:
            parts.append(f"<strong>Command:</strong> {message.metadata.command}")
        else:
            parts.append(f"**Command:** {message.metadata.command}")

    # Add status info
    if message.metadata.status:
        if html:
            parts.append(f"<strong>Status:</strong> {message.metadata.status}")
        else:
            parts.append(f"**Status:** {message.metadata.status}")

    # Add completion status
    if message.metadata.is_complete:
        if html:
            parts.append("<strong>Complete:</strong> Yes")
        else:
            parts.append("**Complete:** Yes")

    if parts:
        return "<br>".join(parts) if html else "\n".join(parts)
    else:
        return ""


def format_system_hints(message: Message, html: bool = False) -> str:
    """
    Format system hints from user messages.

    Args:
        message: The message containing system hints
        html: If True, return HTML formatting; if False, return Markdown

    Returns:
        Formatted system hints string
    """
    if not message.metadata or not message.metadata.system_hints:
        return ""

    hints = message.metadata.system_hints
    if hints:
        if html:
            return f"<strong>System Hints:</strong> {', '.join(hints)}"
        else:
            return f"**System Hints:** {', '.join(hints)}"
    else:
        return ""


def format_model_switcher_deny(message: Message, html: bool = False) -> str:
    """
    Format model switcher deny information.

    Args:
        message: The message containing model switcher deny info
        html: If True, return HTML formatting; if False, return Markdown

    Returns:
        Formatted model switcher deny string
    """
    if not message.metadata or not message.metadata.model_switcher_deny:
        return ""

    parts = []
    if html:
        parts.append("<strong>Model Restrictions:</strong>")
    else:
        parts.append("**Model Restrictions:**")

    for deny in message.metadata.model_switcher_deny:
        if html:
            parts.append(f"<li><strong>{deny.slug}</strong> ({deny.context}): {deny.reason}")
            if deny.description:
                parts.append(f"<br>  {deny.description}")
            parts.append("</li>")
        else:
            parts.append(f"- **{deny.slug}** ({deny.context}): {deny.reason}")
            if deny.description:
                parts.append(f"  {deny.description}")

    if html:
        return f"<ul>{''.join(parts)}</ul>"
    else:
        return "\n".join(parts) 
