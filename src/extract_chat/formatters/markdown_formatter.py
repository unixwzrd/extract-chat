"""
Markdown formatter for ChatGPT conversations.

This module provides a formatter that converts ChatGPT conversations to Markdown format.
"""

import logging
import string
from typing import Any, Dict, List, Optional

from .base import BaseFormatter, FormattingError

logger = logging.getLogger(__name__)


def _ensure_trailing_period(value: str) -> str:
    text = value.strip()
    if not text:
        return ''
    return text if text.endswith('.') else f"{text}."

# ftfy import moved to base class


class MarkdownFormatter(BaseFormatter):
    """Formatter that converts ChatGPT conversations to Markdown format."""

    def get_file_extension(self) -> str:
        """Get the file extension for this format."""
        return "md"

    def get_mime_type(self) -> str:
        """Get the MIME type for this format."""
        return "text/markdown"

    def _format_timestamp(self, timestamp):
        """Format timestamp for display."""
        if timestamp is None:
            return "Unknown"
        try:
            from datetime import datetime
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return str(timestamp)
    
    def _format_elapsed_time(self, start_time, end_time):
        """Format elapsed time between two timestamps."""
        if start_time is None or end_time is None:
            return None
        
        try:
            from datetime import datetime
            start_dt = datetime.fromtimestamp(start_time)
            end_dt = datetime.fromtimestamp(end_time)
            elapsed = end_dt - start_dt
            
            # Calculate time components
            total_seconds = int(elapsed.total_seconds())
            if total_seconds < 0:
                return "Invalid (negative time)"
            
            # Break down into components
            months = 0
            days = elapsed.days
            hours = elapsed.seconds // 3600
            minutes = (elapsed.seconds % 3600) // 60
            seconds = elapsed.seconds % 60
            
            # Calculate months (approximate)
            if days > 30:
                months = days // 30
                days = days % 30
            
            # Build the string
            parts = []
            if months > 0:
                parts.append(f"{months} month{'s' if months != 1 else ''}")
            if days > 0:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            if seconds > 0 or not parts:
                parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
            
            return ", ".join(parts)
            
        except (ValueError, TypeError):
            return "Unknown"

    # Use shared _normalize_text from base class

    def format_document(self, document) -> str:
        """Format a ChatGPT conversation to markdown."""
        return self.format_conversation(document)

    def format_conversation(self, conversation) -> str:
        """
        Format a ChatGPT conversation to Markdown.

        Args:
            conversation: The processed conversation dictionary from ConversationProcessor

        Returns:
            Formatted Markdown string
        """
        try:
            # Build markdown content
            lines = []
            verbose = bool(self.config.get('verbose'))

            # Add title
            if conversation.get('title'):
                lines.append(f"# {conversation['title']}")
                lines.append("")

            # Add conversation ID if available
            if conversation.get('conversation_id'):
                lines.append(f"**Conversation ID:** {conversation['conversation_id']}")
                lines.append("")
            
            # Add timestamps if available
            create_time = conversation.get('create_time')
            update_time = conversation.get('update_time')
            
            if create_time or update_time:
                if create_time:
                    formatted_create_time = self._format_timestamp(create_time)
                    lines.append(f"**Created:** {formatted_create_time}")
                if update_time:
                    formatted_update_time = self._format_timestamp(update_time)
                    lines.append(f"**Last Update:** {formatted_update_time}")
                
                # Add elapsed time if both timestamps are available
                if create_time and update_time:
                    elapsed_time = self._format_elapsed_time(create_time, update_time)
                    if elapsed_time:
                        lines.append(f"**Duration:** {elapsed_time}")
                
                lines.append("")
            
            # Add default model slug if available
            default_model_slug = conversation.get('default_model_slug')
            if default_model_slug:
                lines.append(f"**Default Model:** {default_model_slug}")
                lines.append("")
            
            lines.append("---")
            lines.append("")

            # Add System Context section if there's conversation context
            conversation_context_blocks = []
            conversation_blocks = []
            
            # Process content blocks - separate conversation context from conversation
            content_blocks = conversation.get('content_blocks', [])
            
            logger = logging.getLogger(__name__)
            logger.debug("Total content blocks: %d", len(content_blocks))
            
            for block in content_blocks:
                logger.debug("Processing block - type: %s, turn_id: %s", block.get('type'), block.get('metadata', {}).get('turn_id'))
                if block.get('type') == 'conversation_context':
                    conversation_context_blocks.append(block)
                else:
                    conversation_blocks.append(block)
            
            logger.debug("Conversation context blocks: %d", len(conversation_context_blocks))
            logger.debug("Conversation blocks: %d", len(conversation_blocks))

            # Add System Context section if we have conversation context with content
            context_has_content = False
            for block in conversation_context_blocks:
                content = block.get('content', '')
                if isinstance(content, str) and content.strip():
                    context_has_content = True
                    break
                elif isinstance(content, dict) and content:
                    context_has_content = True
                    break
            
            if conversation_context_blocks and context_has_content:
                lines.append("## System Context")
                lines.append("")
                
                # Format conversation context blocks
                for block in conversation_context_blocks:
                    turn_id = block.get('metadata', {}).get('turn_id')
                    content_length = len(block.get('content', ''))
                    logger.debug("Formatting conversation context block - turn_id: %s, content length: %d", turn_id, content_length)
                    context_lines = self._format_conversation_context_block_dict(block)
                    if context_lines:
                        lines.append(context_lines)
                        lines.append("")
                    else:
                        logger.debug("No context lines returned for block %s", block.get('metadata', {}).get('turn_id'))
                
                lines.append("---")
                lines.append("")

            # Add Conversation section
            lines.append("## Conversation")
            lines.append("")
            
            # Process conversation blocks
            for i, block in enumerate(conversation_blocks):
                block_type = block.get('type', 'text')
                logger.debug("Processing block %d: type=%s, turn_id=%s", i, block_type, block.get('metadata', {}).get('turn_id'))
                
                # Check if this block has internal dialogue
                if 'internal_dialogue' in block and block['internal_dialogue']:
                    logger.debug("Block %d has internal_dialogue with %d items", i, len(block['internal_dialogue']))
                
                # Handle user blocks
                if block_type == 'user':
                    turn_id = block.get('metadata', {}).get('turn_id', 'unknown')
                    timestamp = block.get('metadata', {}).get('timestamp')
                    lines.append(f"### User [Turn: {turn_id}]")
                    if timestamp:
                        lines.append(f"*{self._format_timestamp(timestamp)}*")
                    lines.append("")
                    lines.append(block.get('content', ''))
                    lines.append("")
                
                # Handle assistant blocks with internal dialogue (like the backup)
                elif block_type == 'assistant' and 'internal_dialogue' in block and block['internal_dialogue']:
                    logger.debug("Processing assistant block with internal dialogue: %d items", len(block['internal_dialogue']))
                    
                    # Render assistant label (header)
                    turn_id = block.get('metadata', {}).get('turn_id', 'unknown')
                    timestamp = block.get('metadata', {}).get('timestamp')
                    lines.append(f"### Assistant [Turn: {turn_id}]")
                    if timestamp:
                        lines.append(f"*{self._format_timestamp(timestamp)}*")
                    
                    # Group internal dialogue by request_id
                    internal_groups = self._group_internal_dialogue_by_request(block['internal_dialogue'])
                    
                    # Render each internal dialogue group
                    for request_id, internal_blocks in internal_groups.items():
                        internal_markdown = self._format_internal_dialogue_group(internal_blocks, request_id)
                        if internal_markdown:
                            lines.append(internal_markdown)
                            lines.append("<br>")  # Add HTML break for guaranteed separation
                            lines.append("")  # Add line break after internal dialogue
                    
                    # Now render the assistant's visible response text (content) with inline refs replacement
                    content = block.get('content', '')
                    if content:
                        processed_content = content
                        refs_block = block.get('references_table')
                        if refs_block and refs_block.get('references'):
                            processed_content = self._replace_inline_markers_with_seq(
                                processed_content, refs_block.get('references', [])
                            )
                        lines.append(processed_content)
                        lines.append("")
                        # No per-block references; a single global References section is appended later
                    continue
                
                # Handle assistant blocks (without internal dialogue)
                elif block_type == 'assistant':
                    turn_id = block.get('metadata', {}).get('turn_id', 'unknown')
                    timestamp = block.get('metadata', {}).get('timestamp')
                    lines.append(f"### Assistant [Turn: {turn_id}]")
                    if timestamp:
                        lines.append(f"*{self._format_timestamp(timestamp)}*")
                    
                    # Check if this assistant has internal dialogue attached
                    internal_dialogue = block.get('internal_dialogue', [])
                    if internal_dialogue:
                        # Group internal dialogue by request_id
                        internal_groups = self._group_internal_dialogue_by_request(internal_dialogue)
                        
                        # Render each internal dialogue group
                        for request_id, internal_blocks in internal_groups.items():
                            internal_markdown = self._format_internal_dialogue_group(internal_blocks, request_id)
                            if internal_markdown:
                                lines.append(internal_markdown)
                                lines.append("<br>")  # Add HTML break for guaranteed separation
                                lines.append("")  # Add line break after internal dialogue
                    
                    # Now render the assistant's visible response text (content) with inline refs replacement
                    content = block.get('content', '')
                    if content:
                        refs_block = block.get('references_table')
                        if refs_block and refs_block.get('references'):
                            content = self._replace_inline_markers_with_seq(content, refs_block.get('references', []))
                        lines.append(content)
                        lines.append("")
                    continue
                
                # Handle grouped internal dialogue blocks
                elif block_type == 'grouped_internal_dialogue':
                    formatted_block = self._format_grouped_internal_dialogue_block_dict(block)
                    if formatted_block:
                        lines.append(formatted_block)
                        lines.append("")
                    continue
                
                # Handle other block types (e.g., tool_code, tool_output, etc.)
                else:
                    formatted_block = self._format_block_dict(block)
                    if formatted_block:
                        lines.append(formatted_block)
                        lines.append("")

            # Append a global References section at the very end, aggregating across blocks
            try:
                # Build a single References section from the per-block references_table data only
                global_refs_section = self._generate_global_references_section(conversation_blocks)
                if global_refs_section:
                    lines.append("")
                    lines.append(global_refs_section)
            except Exception as e:
                logger.debug("Failed to build global references section: %s", e)

            # Apply final Unicode normalization to the entire output
            logger.debug("Final lines count: %d", len(lines))
            logger.debug("Looking for internal dialogue in lines...")
            internal_dialogue_count = 0
            for i, line in enumerate(lines):
                if "Internal Dialogue" in line or "Reasoning" in line:
                    internal_dialogue_count += 1
                    if internal_dialogue_count <= 3:  # Only show first 3 instances
                        logger.debug("Found internal dialogue at line %d: %s...", i, line[:50])
            logger.debug("Total internal dialogue instances found: %d", internal_dialogue_count)
            final_output = "\n".join(lines)
            logger.debug("Final output length: %d", len(final_output))
            return self._normalize_text(final_output)

        except Exception as e:
            raise FormattingError(f"Failed to format conversation: {str(e)}", self)
    
    def _generate_references_section(self, citations_data: Dict) -> str:
        """Generate references section from citations data."""
        if not citations_data:
            return ""
        
        # Sort by sequence number
        sorted_keys = sorted(citations_data.keys(), key=lambda k: citations_data[k]['seq'])
        
        lines = ["## References\n"]
        
        for key in sorted_keys:
            info = citations_data[key]
            lines.append(f'<a id="ref-{info["seq"]}"></a>')
            
            if info['title'] and info['url']:
                lines.append(f'**{info["seq"]}.** [{info["title"]}]({info["url"]})')
            elif info['title']:
                lines.append(f'**{info["seq"]}.** {info["title"]}')
            else:
                lines.append(f'**{info["seq"]}.** Reference {info["seq"]}')
            
            if info['text']:
                lines.append(f'_Quoted:_ "{info["text"]}"')
            
            ranges = "; ".join(f"L{s}–L{e}" for s, e in sorted(info['lines']))
            lines.append(f'**Lines:** {ranges}')
            
            if info['attribution']:
                lines.append(f'**Source:** {info["attribution"]}')
            
            lines.append('')
        
        return '\n'.join(lines)

    def _format_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a block dictionary to markdown."""
        block_type = block.get('type', block.get('block_type', 'text'))
        
        if block_type == "text":
            return self._format_text_block_dict(block)
        elif block_type == "code":
            return self._format_code_block_dict(block)
        elif block_type == "tool_call":
            return self._format_tool_call_block_dict(block)
        elif block_type == "internal_dialogue":
            return self._format_internal_dialogue_block_dict(block)
        else:
            return self._format_text_block_dict(block)

    def _format_text_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a text block dictionary to markdown."""
        lines = []
        
        # Add author and timestamp
        author = block.get('type', 'unknown')  # Use type as author for user/assistant blocks
        timestamp = block.get('metadata', {}).get('timestamp')
        turn_id = block.get('metadata', {}).get('turn_id', 'unknown')
        
        logging.getLogger(__name__).debug("Formatting text block - author: %s, turn_id: %s", author, turn_id)
        
        if timestamp:
            lines.append(f"### {author.title()} ({timestamp}) [Turn: {turn_id}]")
        else:
            lines.append(f"### {author.title()} [Turn: {turn_id}]")
        
        lines.append("")
        
        # Add content (with inline citation replacement if references available)
        content = block.get('content', '')
        refs_block = block.get('references_table')
        if content and refs_block and refs_block.get('references'):
            content = self._replace_inline_markers_with_seq(content, refs_block.get('references', []))
        if content:
            formatted_content = self._format_content_with_backticks(content)
            lines.append(formatted_content)
            logging.getLogger(__name__).debug("Added content for %s block %s - length: %d", author, turn_id, len(formatted_content))
        else:
            logging.getLogger(__name__).debug("No content for %s block %s", author, turn_id)
        
        # Do NOT render per-block references here; a single global References section is appended at the end

        result = "\n".join(lines)
        logging.getLogger(__name__).debug("Formatted %s block %s - result length: %d", author, turn_id, len(result))
        return result

    def _replace_inline_markers_with_seq(self, text: str, references: list) -> str:
        """Replace markers with superscript links and cite anchors.

        - Inline marker: 【ref_id†Lstart-Lend】 → <sup id="cite-{unique}"><a href="#ref-{unique}">{seq}</a></sup>
        - This creates forward link to the reference and a cite anchor for back-links.
        """
        try:
            import re as _re

            # Build mapping from key to (seq, unique_id)
            key_to_info = {}
            for r in references:
                key = (int(r.get('ref_id')), int(r.get('start_line')), int(r.get('end_line')))
                key_to_info[key] = (int(r.get('seq')), r.get('unique_id'))

            pattern = r'【(\d+)†L(\d+)-L(\d+)】'

            def _repl(m):
                ref_id = int(m.group(1))
                s = int(m.group(2))
                e = int(m.group(3))
                info = key_to_info.get((ref_id, s, e))
                if not info:
                    return m.group(0)
                seq, unique_id = info
                return f'<sup id="cite-{unique_id}"><a href="#ref-{unique_id}">{seq}</a></sup>'

            return _re.sub(pattern, _repl, text)
        except Exception:
            return text

    # Removed per-block references renderer to avoid duplication; we only render a single global References section

    def _generate_global_references_section(self, conversation_blocks: List[Dict[str, Any]]) -> str:
        """Aggregate references across all assistant blocks and render a final '## References' section.

        Group by (reference_turn_number, ref_id) so anchors remain unique per turn, and list
        citations (by seq) under each reference entry.
        """
        try:
            groups: Dict[int, Dict[str, Any]] = {}

            for block in conversation_blocks:
                if block.get('type') != 'assistant':
                    continue
                refs_block = block.get('references_table') or {}
                refs_list = refs_block.get('references') or []
                turn_num = block.get('metadata', {}).get('reference_turn_number')
                if not refs_list or not turn_num:
                    continue
                for ref in refs_list:
                    ref_id = ref.get('ref_id')
                    if ref_id is None:
                        continue
                    ref_id = int(ref_id)
                    entry = dict(ref)
                    entry['turn_num'] = int(turn_num)
                    group = groups.setdefault(ref_id, {
                        'ref_id': ref_id,
                        'entries': [],
                        'meta': None,
                        'best_score': -1,
                    })
                    group['entries'].append(entry)
                    score = self._score_reference_entry(entry)
                    if score > group['best_score']:
                        group['meta'] = entry
                        group['best_score'] = score

            if not groups:
                return ""

            sorted_groups = sorted(groups.values(), key=self._reference_sort_key)

            out: List[str] = ["## References", ""]
            for index, group in enumerate(sorted_groups, start=1):
                meta = group.get('meta') or {}
                occurrences = sorted(group['entries'], key=lambda e: int(e.get('seq', 10**9)))
                if not occurrences:
                    continue

                anchor_ids = [occ.get('unique_id') for occ in occurrences if occ.get('unique_id')]
                anchor_prefix = ' '.join(
                    f"<a id=\"ref-{uid}\"></a>" for uid in anchor_ids
                )

                citation_label = f"Ref {index}"
                apa_citation = self._format_apa_reference_entry(meta, html=False)

                text_snippet = (meta.get('text') or '').strip().replace('\n', ' ')

                letters = self._backlink_labels(len(occurrences))
                backlinks: List[str] = []
                for idx, occ in enumerate(occurrences):
                    uid = occ.get('unique_id')
                    if not uid:
                        continue
                    label = letters[idx]
                    backlinks.append(f"[ref {label}^](#cite-{uid})")

                pieces = [f"- {citation_label}. {apa_citation}"]
                if text_snippet:
                    pieces.append(f'"{text_snippet}"')
                if backlinks:
                    pieces.append(' '.join(backlinks))
                line = ' '.join(p for p in pieces if p).strip()
                if anchor_prefix:
                    out.append(f"{anchor_prefix} {line}".strip())
                else:
                    out.append(line)
                out.append("")

            return "\n".join(out)
        except Exception:
            return ""

    def _score_reference_entry(self, entry: Dict[str, Any]) -> int:
        score = 0
        if (entry.get('title') or '').strip():
            score += 4
        if (entry.get('url') or '').strip():
            score += 3
        if (entry.get('text') or '').strip():
            score += 2
        if entry.get('attribution'):
            score += 1
        return score

    def _reference_sort_key(self, group: Dict[str, Any]) -> tuple:
        entries = group.get('entries') or []
        if not entries:
            return (10**9, group.get('ref_id', 10**9))
        first = min(entries, key=lambda e: int(e.get('seq', 10**9)))
        return (int(first.get('seq', 10**9)), group.get('ref_id', 10**9))

    def _backlink_labels(self, count: int) -> List[str]:
        labels = []
        alphabet = string.ascii_lowercase
        for idx in range(count):
            label = ''
            n = idx
            while True:
                label = alphabet[n % 26] + label
                n = n // 26 - 1
                if n < 0:
                    break
            labels.append(label)
        return labels

    def _format_apa_reference_entry(self, info: Dict[str, Any], html: bool) -> str:
        """Generate a lightweight APA-style reference string."""
        raw_title = (info.get('title') or '').strip()
        if not raw_title:
            raw_title = (info.get('text') or '').strip()
        if not raw_title:
            raw_title = (info.get('url') or '').strip()
        title = raw_title or 'Untitled source'
        if title == 'Untitled source':
            ref_id = info.get('ref_id')
            turn_num = info.get('turn_num')
            if ref_id is not None:
                if turn_num is not None:
                    title = f"Reference {ref_id} (Turn {turn_num})"
                else:
                    title = f"Reference {ref_id}"
        attribution = (info.get('attribution') or '').strip()
        url = (info.get('url') or '').strip()
        pub_date = info.get('pub_date')
        year = self._extract_year(pub_date)
        year_fragment = f"({year})." if year else "(n.d.)."

        if html:
            if url:
                title_fmt = f"<a href=\"{url}\"><em>{title}</em></a>"
            else:
                title_fmt = f"<em>{title}</em>"
        else:
            if url:
                title_fmt = f"[*{title}*]({url})"
            else:
                title_fmt = f"*{title}*"

        parts: List[str] = []
        parts.append(year_fragment)
        parts.append(title_fmt)
        # URL is already incorporated via title hyperlink when available

        return ' '.join(p.strip() for p in parts if p).strip()

    def _extract_year(self, value: Any) -> Optional[str]:
        if not value:
            return None
        try:
            import re as _re
            match = _re.search(r'(\\d{4})', str(value))
            if match:
                return match.group(1)
        except Exception:
            return None
        return None

    def _format_code_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a code block dictionary to markdown."""
        lines = []
        
        # Add author and timestamp
        author = block.get('author', 'unknown')
        timestamp = block.get('metadata', {}).get('timestamp')
        language = block.get('language', '')
        block_id = block.get('block_id', 'unknown')
        
        if timestamp:
            lines.append(f"### {author.title()} ({timestamp}) [Turn: {block_id}]")
        else:
            lines.append(f"### {author.title()} [Turn: {block_id}]")
        
        lines.append("")
        
        # Add code content
        content = block.get('content', '')
        if content:
            # Handle language specification - skip "unknown" and empty languages
            if language and language.lower() not in ['unknown', '']:
                lines.append(f"```{language}")
            else:
                lines.append("```")
            lines.append(content)
            lines.append("```")
            lines.append("")
        
        return "\n".join(lines)

    def _format_tool_call_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a tool call block dictionary to markdown."""
        lines = []
        
        # Add tool name and timestamp
        tool_name = block.get('tool_name', 'unknown_tool')
        timestamp = block.get('metadata', {}).get('timestamp')
        block_id = block.get('block_id', 'unknown')
        
        if timestamp:
            lines.append(f"### Tool: {tool_name} ({self._format_timestamp(timestamp)}) [Turn: {block_id}]")
        else:
            lines.append(f"### Tool: {tool_name} [Turn: {block_id}]")
        
        lines.append("")
        
        # Add input data if available and meaningful
        input_data = block.get('input_data')
        if input_data and input_data != "{}" and input_data != "null":
            # Try to format JSON nicely
            try:
                import json
                parsed = json.loads(str(input_data))
                formatted_json = json.dumps(parsed, indent=2)
                lines.append("**Input:**")
                lines.append("")
                lines.append("```json")
                lines.append(formatted_json)
                lines.append("```")
                lines.append("")
            except (ValueError, TypeError):
                # Fallback to raw string if not valid JSON
                if len(str(input_data)) > 10:  # Only show if substantial
                    lines.append("**Input:**")
                    lines.append("")
                    lines.append("```json")
                    lines.append(str(input_data))
                    lines.append("```")
                    lines.append("")
        
        # Add output content if meaningful
        content = block.get('content', '')
        if content and content.strip() and content not in ['{}', 'null', '']:
            lines.append("**Output:**")
            normalized_content = self._normalize_text(content)
            lines.append(normalized_content)
        
        return "\n".join(lines)

    def _format_assistant_with_tool_dict(self, assistant_block: Dict[str, Any], tool_block: Dict[str, Any]) -> str:
        """Format an assistant message with its associated tool call."""
        lines = []
        
        # Format assistant message
        assistant_lines = self._format_text_block_dict(assistant_block)
        lines.append(assistant_lines)
        lines.append("")
        
        # Format tool call
        tool_lines = self._format_tool_call_block_dict(tool_block)
        lines.append(tool_lines)
        
        return "\n".join(lines)

    def _format_conversation_context_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a conversation context block dictionary to markdown."""
        lines = []
        
        # Get content and metadata sections
        content = block.get('content', {})
        metadata = block.get('metadata', {})
        
        # User profile and instructions are in the content section
        user_profile = content.get('user_profile', '') if isinstance(content, dict) else ''
        user_instructions = content.get('user_instructions', '') if isinstance(content, dict) else ''
        
        # About user and model are in the metadata section
        about_user = metadata.get('about_user', '')
        about_model = metadata.get('about_model', '')
        
        # Add User Profile section
        if user_profile:
            lines.append("### User Profile")
            lines.append("")
            # Fix triple backticks in user profile
            fixed_profile = self._fix_triple_backticks_in_context(user_profile)
            lines.append(fixed_profile)
            lines.append("")
        
        # Add User Instructions section
        if user_instructions:
            lines.append("### User Instructions")
            lines.append("")
            # Fix triple backticks in user instructions
            fixed_instructions = self._fix_triple_backticks_in_context(user_instructions)
            lines.append(fixed_instructions)
            lines.append("")
        
        # Add About The User section
        if about_user:
            lines.append("### About The User")
            lines.append("")
            # Fix triple backticks in about user
            fixed_about_user = self._fix_triple_backticks_in_context(about_user)
            lines.append(fixed_about_user)
            lines.append("")
        
        # Add About The Model section
        if about_model:
            lines.append("### About The Model")
            lines.append("")
            # Fix triple backticks in about model
            fixed_about_model = self._fix_triple_backticks_in_context(about_model)
            lines.append(fixed_about_model)
            lines.append("")
        
        return "\n".join(lines)

    def _format_content_with_backticks(self, content: str) -> str:
        """Format content with proper backtick handling."""
        # This is a simplified version - in a full implementation,
        # you might want to detect code blocks and format them properly
        return content

    def _fix_triple_backticks_in_context(self, text: str) -> str:
        """
        Fix triple backticks specifically for conversation context sections.
        
        Args:
            text: Text containing triple backticks
            
        Returns:
            Text with properly formatted triple backticks
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
                # Add newline before if missing
                if not part.startswith('\n'):
                    part = '\n' + part
                
                # Add newline after if missing
                if not part.endswith('\n'):
                    part = part + '\n'
                
                result_parts.append('```' + part + '```')
            else:
                # This is content between backtick blocks (even indices)
                result_parts.append(part)
        
        return ''.join(result_parts)
    
    def _format_internal_dialogue_block_dict(self, block: Dict[str, Any]) -> str:
        """Format an internal dialogue block as a regular turn."""
        if self.config.get('verbose'):
            print(f"DEBUG: _format_internal_dialogue_block_dict called with block: {block.get('role', 'unknown')}")
        turn_id = block.get('metadata', {}).get('turn_id', 'unknown')
        role = block.get('role', 'assistant')
        content = block.get('content', '')
        timestamp = block.get('metadata', {}).get('timestamp')
        additional_info = block.get('additional_info', {})
        
        if self.config.get('verbose'):
            print(f"DEBUG: Internal block - role: {role}, content length: {len(content)}")
        
        # Format timestamp
        timestamp_str = ""
        if timestamp:
            timestamp_str = f" ({timestamp})"
        
        # Format as a regular turn
        lines = []
        lines.append(f"### {role.title()}{timestamp_str} [Turn: {turn_id}]")
        
        # Add comprehensive metadata if available
        if additional_info:
            metadata_lines = []
            
            # Basic metadata
            if additional_info.get('url'):
                metadata_lines.append(f"**URL:** {additional_info['url']}")
            if additional_info.get('domain'):
                metadata_lines.append(f"**Domain:** {additional_info['domain']}")
            if additional_info.get('title'):
                metadata_lines.append(f"**Title:** {additional_info['title']}")
            
            # Author and source metadata
            if additional_info.get('real_author'):
                metadata_lines.append(f"**Real Author:** {additional_info['real_author']}")
            if additional_info.get('source'):
                metadata_lines.append(f"**Source:** {additional_info['source']}")
            if additional_info.get('sonicberry_model_id'):
                metadata_lines.append(f"**Model ID:** {additional_info['sonicberry_model_id']}")
            
            # Processing metadata
            if additional_info.get('reasoning_status'):
                metadata_lines.append(f"**Reasoning Status:** {additional_info['reasoning_status']}")
            if additional_info.get('search_source'):
                metadata_lines.append(f"**Search Source:** {additional_info['search_source']}")
            if additional_info.get('model_slug'):
                metadata_lines.append(f"**Model Slug:** {additional_info['model_slug']}")
            if additional_info.get('recipient'):
                metadata_lines.append(f"**Recipient:** {additional_info['recipient']}")
            if additional_info.get('parent_id'):
                metadata_lines.append(f"**Parent ID:** {additional_info['parent_id']}")
            
            # Search queries (if available)
            if additional_info.get('search_queries'):
                queries = additional_info['search_queries']
                if isinstance(queries, list) and queries:
                    query_texts = []
                    for query in queries:
                        if isinstance(query, dict) and 'q' in query:
                            query_texts.append(query['q'])
                    if query_texts:
                        metadata_lines.append(f"**Search Queries:** {', '.join(query_texts)}")
            
            # Citations and references
            if additional_info.get('citations'):
                metadata_lines.append(f"**Citations:** {len(additional_info['citations'])} items")
            if additional_info.get('content_references'):
                metadata_lines.append(f"**Content References:** {len(additional_info['content_references'])} items")
            
            # Visual indicators
            if additional_info.get('visually_hidden'):
                metadata_lines.append("**Visually Hidden:** True")
            
            if metadata_lines:
                lines.append("")
                lines.append("**Metadata:**")
                for metadata_line in metadata_lines:
                    lines.append(f"- {metadata_line}")
        
        lines.append("")
        lines.append(content)
        lines.append("")
        
        result = "\n".join(lines)
        if self.config.get('verbose'):
            print(f"DEBUG: _format_internal_dialogue_block_dict returning {len(result)} chars")
        return result

    def _format_grouped_internal_dialogue_block_dict(self, block: Dict[str, Any]) -> str:
        """Format a grouped internal dialogue block with window shade effect."""
        content = block.get('content', {})
        metadata = block.get('metadata', {})
        internal_blocks = content.get('internal_blocks', [])
        request_id = content.get('request_id', 'unknown')
        
        if not internal_blocks:
            return ""
        
        # Create window shade effect
        lines = []
        lines.append('<details>')
        
        # Create summary with request ID and block count
        block_count = len(internal_blocks)
        first_timestamp = metadata.get('first_timestamp')
        last_timestamp = metadata.get('last_timestamp')
        
        summary_text = f"**Internal Dialogue** - Request: {request_id} ({block_count} steps)"
        if first_timestamp and last_timestamp:
            summary_text += f" - {self._format_timestamp(first_timestamp)} to {self._format_timestamp(last_timestamp)}"
        
        lines.append(f'<summary>{summary_text}</summary>')
        lines.append("")
        
        # Format each internal block
        for i, internal_block in enumerate(internal_blocks, 1):
            internal_content = internal_block.get('content', {})
            internal_metadata = internal_block.get('metadata', {})
            
            content_type = internal_content.get('content_type', 'unknown')
            turn_id = internal_metadata.get('turn_id', 'unknown')
            timestamp = internal_metadata.get('timestamp')
            author_role = internal_metadata.get('author_role', 'unknown')
            real_author = internal_metadata.get('real_author')
            model_slug = internal_metadata.get('model_slug')
            status = internal_metadata.get('status', 'unknown')
            
            # Create header for this internal step
            step_header = f"**Step {i}: {content_type.title()}**"
            if timestamp:
                step_header += f" ({self._format_timestamp(timestamp)})"
            step_header += f" [Turn: {turn_id}]"
            
            lines.append(f"### {step_header}")
            lines.append("")
            
            # Add metadata
            metadata_lines = []
            if author_role != 'unknown':
                metadata_lines.append(f"**Role:** {author_role}")
            if real_author:
                metadata_lines.append(f"**Real Author:** {real_author}")
            if model_slug:
                metadata_lines.append(f"**Model:** {model_slug}")
            if status != 'unknown':
                metadata_lines.append(f"**Status:** {status}")
            
            # Add search queries if available
            search_queries = internal_content.get('search_queries', [])
            if search_queries:
                query_texts = []
                for query in search_queries:
                    if isinstance(query, dict) and 'q' in query:
                        query_texts.append(query['q'])
                if query_texts:
                    metadata_lines.append(f"**Search Queries:** {', '.join(query_texts)}")
            
            # Add search results if available
            search_results = internal_content.get('search_result_groups', [])
            if search_results:
                result_count = sum(len(group.get('entries', [])) for group in search_results)
                metadata_lines.append(f"**Search Results:** {result_count} items")
                
                # Show first few results
                for group in search_results[:2]:  # Limit to first 2 groups
                    domain = group.get('domain', 'unknown')
                    entries = group.get('entries', [])
                    if entries:
                        metadata_lines.append(f"  - **{domain}:** {len(entries)} results")
                        for entry in entries[:2]:  # Limit to first 2 entries per group
                            title = entry.get('title', 'No title')
                            metadata_lines.append(f"    - {title[:60]}...")
            
            if metadata_lines:
                for metadata_line in metadata_lines:
                    lines.append(metadata_line)
                lines.append("")
            
            # Add content
            text_content = internal_content.get('text', '')
            if text_content:
                # Handle different content types
                if content_type == 'code':
                    language = internal_content.get('language', '')
                    if language and language != 'unknown':
                        lines.append(f"```{language}")
                    else:
                        lines.append("```")
                    lines.append(text_content)
                    lines.append("```")
                else:
                    lines.append(text_content)
            
            # Add thoughts if available
            thoughts = internal_content.get('thoughts', [])
            if thoughts:
                lines.append("")
                lines.append("**Thoughts:**")
                for thought in thoughts:
                    lines.append(f"- {thought}")
            
            lines.append("")
        
        lines.append('</details>')
        lines.append("")  # Add line break after details tag
        
        return "\n".join(lines)

    def _group_internal_dialogue_by_request(self, internal_blocks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group internal dialogue blocks by request_id."""
        # Since we're using state-based processing, all internal dialogue should be in one group
        groups = {}
        if internal_blocks:
            # Use a single group for all internal dialogue
            groups['internal_dialogue'] = internal_blocks
        
        # Sort blocks by timestamp
        for request_id in groups:
            groups[request_id].sort(key=lambda x: x.get('metadata', {}).get('timestamp', 0))
        
        return groups

    def _format_internal_dialogue_group(self, internal_blocks: List[Dict[str, Any]], request_id: str) -> str:
        """Format a group of internal dialogue blocks with window shade effect."""
        if not internal_blocks:
            return ""
        
        # Create window shade effect
        lines = []
        lines.append('<details>')
        
        # Create summary with request ID and block count
        block_count = len(internal_blocks)
        first_timestamp = internal_blocks[0].get('metadata', {}).get('timestamp') if internal_blocks else None
        last_timestamp = internal_blocks[-1].get('metadata', {}).get('timestamp') if internal_blocks else None
        
        if request_id == 'internal_dialogue':
            summary_text = f"**Internal Dialogue** ({block_count} steps)"
        else:
            summary_text = f"**Internal Dialogue** - Request: {request_id} ({block_count} steps)"
        
        if first_timestamp and last_timestamp:
            summary_text += f" - {self._format_timestamp(first_timestamp)} to {self._format_timestamp(last_timestamp)}"
        
        lines.append(f'<summary>{summary_text}</summary>')
        lines.append("")
        
        # Format each internal block
        for i, internal_block in enumerate(internal_blocks, 1):
            internal_content = internal_block.get('content', {})
            internal_metadata = internal_block.get('metadata', {})
            
            content_type = internal_content.get('content_type', 'unknown')
            turn_id = internal_metadata.get('turn_id', 'unknown')
            timestamp = internal_metadata.get('timestamp')
            author_role = internal_metadata.get('author_role', 'unknown')
            real_author = internal_metadata.get('real_author')
            model_slug = internal_metadata.get('model_slug')
            status = internal_metadata.get('status', 'unknown')
            
            # Create header for this internal step
            step_header = f"**Step {i}: {content_type.title()}**"
            if timestamp:
                step_header += f" ({self._format_timestamp(timestamp)})"
            step_header += f" [Turn: {turn_id}]"
            
            lines.append(f"### {step_header}")
            lines.append("")
            
            # Add metadata
            metadata_lines = []
            if author_role != 'unknown':
                metadata_lines.append(f"**Role:** {author_role}")
            if real_author:
                metadata_lines.append(f"**Real Author:** {real_author}")
            if model_slug:
                metadata_lines.append(f"**Model:** {model_slug}")
            if status != 'unknown':
                metadata_lines.append(f"**Status:** {status}")
            
            # Add search queries if available
            search_queries = internal_content.get('search_queries', [])
            if search_queries:
                query_texts = []
                for query in search_queries:
                    if isinstance(query, dict) and 'q' in query:
                        query_texts.append(query['q'])
                if query_texts:
                    metadata_lines.append(f"**Search Queries:** {', '.join(query_texts)}")
            
            # Add search results if available
            search_results = internal_content.get('search_result_groups', [])
            if search_results:
                result_count = sum(len(group.get('entries', [])) for group in search_results)
                metadata_lines.append(f"**Search Results:** {result_count} items")
                
                # Show first few results
                for group in search_results[:2]:  # Limit to first 2 groups
                    domain = group.get('domain', 'unknown')
                    entries = group.get('entries', [])
                    if entries:
                        metadata_lines.append(f"  - **{domain}:** {len(entries)} results")
                        for entry in entries[:2]:  # Limit to first 2 entries per group
                            title = entry.get('title', 'No title')
                            metadata_lines.append(f"    - {title[:60]}...")
            
            if metadata_lines:
                for metadata_line in metadata_lines:
                    lines.append(metadata_line)
                lines.append("")
            
            # Add content
            text_content = internal_content.get('text', '')
            if text_content:
                # Handle different content types
                if content_type == 'code':
                    language = internal_content.get('language', '')
                    if language and language != 'unknown':
                        lines.append(f"```{language}")
                    else:
                        lines.append("```")
                    lines.append(text_content)
                    lines.append("```")
                else:
                    lines.append(text_content)
            
            # Add thoughts if available
            thoughts = internal_content.get('thoughts', [])
            if thoughts:
                lines.append("")
                lines.append("**Thoughts:**")
                for thought in thoughts:
                    lines.append(f"- {thought}")
            
            lines.append("")
        
        lines.append('</details>')
        lines.append("")  # Add line break after details tag
        
        return "\n".join(lines)
