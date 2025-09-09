"""
Structured Input Schemas for ChatGPT JSON Processing (V2).

This module provides Pydantic models that exactly match the ChatGPT JSON structure,
allowing automatic validation and transformation without manual processing.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

import ftfy
from pydantic import BaseModel, Field


def _normalize_text(text: str) -> str:
    """Normalize text using ftfy to clean up Unicode issues."""
    if not text:
        return text
    return ftfy.fix_text(text, normalization='NFKC')


# ============================================================================
# COMPREHENSIVE CHATGPT JSON STRUCTURE
# ============================================================================

class MessageAuthor(BaseModel):
    """Message author structure with comprehensive metadata."""
    role: Literal["system", "user", "assistant", "tool"]
    name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Critical author metadata fields for internal dialogue detection
    real_author: Optional[str] = None
    source: Optional[str] = None
    sonicberry_model_id: Optional[str] = None

    class Config:
        extra = "allow"


class MessageContent(BaseModel):
    """Message content structure with comprehensive fields and metadata."""
    content_type: Optional[str] = "text"
    parts: Optional[List[Union[str, Dict[str, Any]]]] = None
    text: Optional[str] = None
    language: Optional[str] = None
    
    # Special content type fields
    user_profile: Optional[str] = None
    user_instructions: Optional[str] = None
    model_set_context: Optional[str] = None
    repository: Optional[str] = None
    repo_summary: Optional[str] = None
    structured_context: Optional[str] = None
    thoughts: Optional[Union[str, List[Any]]] = None
    source_analysis_msg_id: Optional[str] = None
    response_format_name: Optional[str] = None
    content: Optional[str] = None
    
    # Tool-specific fields
    result: Optional[str] = None
    summary: Optional[str] = None
    assets: Optional[List[Dict[str, Any]]] = None
    tether_id: Optional[str] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    title: Optional[str] = None
    
    # Critical content fields for internal dialogue detection
    context_parts: Optional[List[Dict[str, Any]]] = None
    custom_instructions: Optional[str] = None
    name: Optional[str] = None
    workspaces: Optional[List[Dict[str, Any]]] = None

    class Config:
        extra = "allow"


class Message(BaseModel):
    """Message structure containing author, content, and comprehensive metadata."""
    id: Optional[str] = None
    author: MessageAuthor
    content: MessageContent
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    status: Optional[str] = None
    end_turn: Optional[bool] = None
    weight: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    recipient: Optional[str] = None
    channel: Optional[str] = None
    
    # Critical metadata fields for internal dialogue detection
    # These are the most important fields we discovered from the schema analysis
    is_visually_hidden_from_conversation: Optional[bool] = None
    is_loading_message: Optional[bool] = None
    model_slug: Optional[str] = None
    rebase_system_message: Optional[bool] = None
    is_user_system_message: Optional[bool] = None
    reasoning_status: Optional[str] = None
    search_turns_count: Optional[int] = None
    search_source: Optional[str] = None
    client_reported_search_source: Optional[str] = None
    search_queries: Optional[List[Dict[str, Any]]] = None
    search_display_string: Optional[str] = None
    searched_display_string: Optional[str] = None
    search_result_groups: Optional[List[Dict[str, Any]]] = None
    debug_sonic_thread_id: Optional[str] = None
    system_hints: Optional[List[str]] = None
    is_async_task_result_message: Optional[bool] = None
    b1de6e2_s: Optional[bool] = None
    command: Optional[str] = None
    async_task_id: Optional[str] = None
    async_task_conversation_id: Optional[str] = None
    async_task_created_at: Optional[str] = None
    deep_research_version: Optional[str] = None
    b1de6e2_rm: Optional[bool] = None
    permissions: Optional[List[Dict[str, Any]]] = None
    user_context_message_data: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class Turn(BaseModel):
    """Turn structure containing a message and parent-child relationships."""
    id: Optional[str] = None
    message: Optional[Message] = None
    parent: Optional[str] = None
    children: List[str] = Field(default_factory=list)
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    archived: Optional[bool] = None
    pinned: Optional[bool] = None
    
    class Config:
        extra = "allow"


class Conversation(BaseModel):
    """Conversation structure - comprehensive with all metadata fields."""
    title: Optional[str] = None
    create_time: Optional[float] = None
    update_time: Optional[float] = None
    mapping: Dict[str, Turn] = Field(default_factory=dict)
    moderation_results: Optional[List[Dict[str, Any]]] = None
    current_node: Optional[str] = None
    plugin_ids: Optional[List[str]] = None
    conversation_id: Optional[str] = None
    conversation_template_id: Optional[str] = None
    gizmo_id: Optional[str] = None
    gizmo_type: Optional[str] = None
    is_archived: Optional[bool] = None
    is_starred: Optional[bool] = None
    safe_urls: Optional[List[str]] = None
    blocked_urls: Optional[List[str]] = None
    default_model_slug: Optional[str] = None
    conversation_origin: Optional[str] = None
    voice: Optional[str] = None
    async_status: Optional[str] = None
    disabled_tool_ids: Optional[List[str]] = None
    is_do_not_remember: Optional[bool] = None
    memory_scope: Optional[str] = None
    sugar_item_id: Optional[str] = None
    
    class Config:
        extra = "allow"

    def get_conversation_flow_turns(self) -> List[tuple[str, Turn, Optional[datetime]]]:
        """Get turns following parent-child relationships to maintain conversation flow."""
        turns_with_times = []
        processed_turns = set()
        
        # Find the root turn (turn with no parent or parent not in mapping)
        root_turns = []
        for turn_id, turn in self.mapping.items():
            if not turn.parent or turn.parent not in self.mapping:
                root_turns.append(turn_id)
        
        # If no clear root, use the first turn
        if not root_turns:
            root_turns = [list(self.mapping.keys())[0]]
        
        # Walk through the conversation tree starting from each root
        for root_turn_id in root_turns:
            self._walk_conversation_tree(root_turn_id, turns_with_times, processed_turns)
        
        return turns_with_times
    
    def _walk_conversation_tree(
        self, 
        turn_id: str, 
        turns_with_times: List[tuple[str, Turn, Optional[datetime]]], 
        processed_turns: set
    ):
        """Recursively walk through the conversation tree following parent-child relationships."""
        if turn_id in processed_turns or turn_id not in self.mapping:
            return
        
        processed_turns.add(turn_id)
        turn = self.mapping[turn_id]
        
        # Extract create_time from turn or message
        create_time = None
        if turn.create_time:
            create_time = turn.create_time
        elif turn.message and turn.message.create_time:
            create_time = turn.message.create_time
        
        # Convert to datetime
        timestamp = datetime.fromtimestamp(create_time) if create_time else None
        
        turns_with_times.append((turn_id, turn, timestamp))
        
        # Process children in order
        for child_id in turn.children:
            self._walk_conversation_tree(child_id, turns_with_times, processed_turns)
    
    def get_chronological_turns(self) -> List[tuple[str, Turn, Optional[datetime]]]:
        """Get turns sorted by create_time with timestamps converted to datetime."""
        turns_with_times = []
        
        for turn_id, turn in self.mapping.items():
            # Extract create_time from turn or message
            create_time = None
            if turn.create_time:
                create_time = turn.create_time
            elif turn.message and turn.message.create_time:
                create_time = turn.message.create_time
            
            # Convert to datetime
            timestamp = datetime.fromtimestamp(create_time) if create_time else None
            
            turns_with_times.append((turn_id, turn, timestamp))
        
        # Sort by create_time (None values go first)
        turns_with_times.sort(key=lambda x: x[2] or datetime.min)
        return turns_with_times

    def get_messages_by_role(self, role: str) -> List[tuple[str, Message]]:
        """Get all messages with a specific role."""
        messages = []
        for turn_id, turn in self.mapping.items():
            if turn.message and turn.message.author.role == role:
                messages.append((turn_id, turn.message))
        return messages

    def get_tool_messages(self) -> List[tuple[str, Message]]:
        """Get all tool messages."""
        return self.get_messages_by_role("tool")

    def get_user_context_messages(self) -> List[tuple[str, Message]]:
        """Get messages with user context (user_profile, user_instructions)."""
        messages = []
        for turn_id, turn in self.mapping.items():
            if turn.message and turn.message.content:
                content = turn.message.content
                if (content.user_profile or content.user_instructions or
                        (turn.message.metadata and turn.message.metadata.get('user_context_message_data'))):
                    messages.append((turn_id, turn.message))
        return messages

    def get_metadata(self) -> Dict[str, Any]:
        """Get conversation metadata for formatting."""
        return {
            'title': self.title or "ChatGPT Conversation",
            'conversation_id': self.conversation_id,
            'create_time': datetime.fromtimestamp(self.create_time) if self.create_time else None,
            'update_time': datetime.fromtimestamp(self.update_time) if self.update_time else None,
            'model': self.default_model_slug
        }

    def get_content_blocks(self) -> List[Dict[str, Any]]:
        """Get content blocks ready for formatting."""
        blocks = []
        conversation_flow_turns = self.get_conversation_flow_turns()
        
        # Group turns by their relationship to create hierarchical structure
        grouped_blocks = self._group_related_turns(conversation_flow_turns)
        
        print(f"DEBUG: get_content_blocks: {len(grouped_blocks)} grouped blocks")
        for i, block in enumerate(grouped_blocks):
            if block:
                block_type = block.get('block_type', 'unknown')
                author = block.get('author', 'None')
                print(f"DEBUG: get_content_blocks: block {i}: type={block_type}, author={author}")
                blocks.append(block)
            else:
                print(f"DEBUG: get_content_blocks: block {i}: None (skipping)")
        
        print(f"DEBUG: get_content_blocks: returning {len(blocks)} blocks")
        return blocks
    
    def _get_content_text(self, message: Message) -> str:
        """Extract text content from a message for duplicate detection."""
        if message.content.text:
            return message.content.text
        elif message.content.parts:
            return " ".join(str(part) for part in message.content.parts if part)
        return ""
    
    def _is_internal_dialogue(self, message: Message) -> bool:
        """Check if message is internal dialogue using metadata from the comprehensive schema."""
        if not message.content:
            return False
        
        # Access metadata directly from the message
        metadata = message.metadata or {}
        author_metadata = message.author.metadata or {}
        
        # Primary identifier: is_visually_hidden_from_conversation
        if metadata.get('is_visually_hidden_from_conversation', False):
            print(f"DEBUG: Internal dialogue detected - is_visually_hidden_from_conversation: True for turn {message.id}")
            return True
        
        # Tool messages are internal
        if message.author.role == "tool":
            print(f"DEBUG: Internal dialogue detected - tool role for turn {message.id}")
            return True
        
        # System messages are internal
        if message.author.role == "system":
            print(f"DEBUG: Internal dialogue detected - system role for turn {message.id}")
            return True
        
        # Check for tool-generated content
        if author_metadata.get('real_author', '').startswith('tool:'):
            print(f"DEBUG: Internal dialogue detected - real_author: {author_metadata.get('real_author')} for turn {message.id}")
            return True
        
        if author_metadata.get('source') in ['sonic_tool', 'tool']:
            print(f"DEBUG: Internal dialogue detected - source: {author_metadata.get('source')} for turn {message.id}")
            return True
        
        # Check content type for internal processing
        if message.content.content_type in ["user_editable_context", "model_editable_context", "thoughts", "reasoning_recap"]:
            print(f"DEBUG: Internal dialogue detected - content_type: {message.content.content_type} for turn {message.id}")
            return True
        
        # Code content types are internal
        if message.content.content_type == "code":
            print(f"DEBUG: Internal dialogue detected - content_type: code for turn {message.id}")
            return True
        
        # Check for system message indicators
        if metadata.get('rebase_system_message', False):
            print(f"DEBUG: Internal dialogue detected - rebase_system_message: True for turn {message.id}")
            return True
        
        if metadata.get('is_user_system_message', False):
            print(f"DEBUG: Internal dialogue detected - is_user_system_message: True for turn {message.id}")
            return True
        
        # Check for tool recipient
        if message.recipient and (
            message.recipient.startswith('research_') or 
            message.recipient.endswith('_tool') or 
            '_tool.' in message.recipient
        ):
            print(f"DEBUG: Internal dialogue detected - recipient: {message.recipient} for turn {message.id}")
            return True
        
        # Check for research model slug
        if metadata.get('model_slug') == 'research':
            print(f"DEBUG: Internal dialogue detected - model_slug: research for turn {message.id}")
            return True
        
        # Check for loading message indicator
        if metadata.get('is_loading_message', False):
            print(f"DEBUG: Internal dialogue detected - is_loading_message: True for turn {message.id}")
            return True
        
        # Check for async task result messages
        if metadata.get('is_async_task_result_message', False):
            print(f"DEBUG: Internal dialogue detected - is_async_task_result_message: True for turn {message.id}")
            return True
        
        # Check for reasoning status
        if metadata.get('reasoning_status'):
            print(f"DEBUG: Internal dialogue detected - reasoning_status: {metadata.get('reasoning_status')} for turn {message.id}")
            return True
        
        # Check for search-related indicators
        if metadata.get('search_source') or metadata.get('client_reported_search_source'):
            print(f"DEBUG: Internal dialogue detected - search source for turn {message.id}")
            return True
        
        if metadata.get('search_turns_count') or metadata.get('search_queries') or metadata.get('search_result_groups'):
            print(f"DEBUG: Internal dialogue detected - search data for turn {message.id}")
            return True
        
        # Check for debug indicators
        if metadata.get('debug_sonic_thread_id') or metadata.get('b1de6e2_s') or metadata.get('b1de6e2_rm'):
            print(f"DEBUG: Internal dialogue detected - debug indicators for turn {message.id}")
            return True
        
        # Check for command or async task indicators
        if metadata.get('command') or metadata.get('async_task_id') or metadata.get('async_task_conversation_id'):
            print(f"DEBUG: Internal dialogue detected - command/async indicators for turn {message.id}")
            return True
        
        # Check for JSON content that contains internal processing indicators
        if message.content.text and message.content.text.strip().startswith('{'):
            print(f"DEBUG: Found JSON content in turn {message.id}, attempting to parse...")
            try:
                import json
                content_json = json.loads(message.content.text)
                print(f"DEBUG: Successfully parsed JSON for turn {message.id}")
                # Check for internal processing indicators in JSON
                internal_indicators = ['task_violates_safety_guidelines', 'user_def_doesnt_want_research', 'response', 'prompt']
                if any(key in content_json for key in internal_indicators):
                    print(f"DEBUG: Internal dialogue detected - JSON with internal processing indicators for turn {message.id}")
                    return True
                else:
                    print(f"DEBUG: JSON parsed but no internal indicators found for turn {message.id}")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"DEBUG: Failed to parse JSON for turn {message.id}: {e}")
                pass  # Not valid JSON, continue with other checks
        
        return False
    
    def _group_related_turns(self, turns: List[tuple[str, Turn, Optional[datetime]]]) -> List[Dict[str, Any]]:
        """Group related turns together to create hierarchical conversation structure."""
        blocks = []
        pending_internal_blocks = []  # Collect internal dialogue to attach to next assistant response
        used_internal_turn_ids = set()  # Track which internal turns have been used
        seen_user_content = set()  # Track user content to avoid duplicates
        
        print(f"DEBUG: Processing {len(turns)} turns for grouping")
        
        # Process turns chronologically
        for turn_id, turn, timestamp in turns:
            if not turn.message:
                continue
            
            print(f"DEBUG: Processing turn {turn_id} - role: {turn.message.author.role}")
            
            # Check if this is conversation context first
            if self._is_conversation_context_message(turn.message):
                print(f"DEBUG: Turn {turn_id} is conversation context")
                block = self._create_conversation_context_block(turn_id, turn.message, timestamp)
                if block:
                    blocks.append(block)
                continue
            
            # Check if this is internal dialogue
            if self._is_internal_dialogue(turn.message):
                print(f"DEBUG: Turn {turn_id} is internal dialogue")
                internal_block = self._create_internal_dialogue_block(turn_id, turn.message)
                if internal_block:
                    pending_internal_blocks.append(internal_block)
                    used_internal_turn_ids.add(turn_id)  # Mark as used
                    print(f"DEBUG: Added internal block to pending_internal_blocks, now has {len(pending_internal_blocks)} blocks")
                continue
            
            # This is an external turn (user/assistant)
            print(f"DEBUG: Turn {turn_id} is external dialogue - role: {turn.message.author.role}")
            
            # For user turns, check for duplicates
            if turn.message.author.role == "user":
                content_text = self._get_content_text(turn.message)
                if content_text in seen_user_content:
                    print(f"DEBUG: Skipping duplicate user content for turn {turn_id}")
                    continue
                seen_user_content.add(content_text)
            
            # Create main content block
            main_block = self._create_content_block(turn_id, turn.message, timestamp)
            if not main_block:
                continue
            
            # For assistant turns, also check for internal dialogue in child turns
            if turn.message.author.role == "assistant":
                print(f"DEBUG: Checking for internal dialogue in children of turn {turn_id}")
                child_internal_blocks = self._get_internal_dialogue_blocks(turn_id, turn, used_internal_turn_ids)
                if child_internal_blocks:
                    print(f"DEBUG: Found {len(child_internal_blocks)} internal blocks in children")
                    pending_internal_blocks.extend(child_internal_blocks)
            
            # If this is an assistant response and we have pending internal blocks, attach them
            if turn.message.author.role == "assistant" and pending_internal_blocks:
                print(f"DEBUG: Attaching {len(pending_internal_blocks)} pending internal blocks to assistant response {turn_id}")
                # Attach internal dialogue directly to the assistant block
                main_block['internal_dialogue'] = pending_internal_blocks.copy()
                pending_internal_blocks.clear()  # Clear for next assistant response
            
            blocks.append(main_block)
        
        print(f"DEBUG: Created {len(blocks)} total blocks")
        return blocks
    
    def _get_internal_dialogue_blocks(
        self, parent_turn_id: str, parent_turn: Turn, used_internal_turn_ids: set
    ) -> List[Dict[str, Any]]:
        """Get internal dialogue blocks that are descendants of the given turn."""
        internal_blocks = []
        processed_turns = set()
        
        def traverse_subtree(turn_id: str):
            if turn_id in processed_turns or turn_id not in self.mapping:
                return
            
            processed_turns.add(turn_id)
            turn = self.mapping[turn_id]
            
            if not turn.message:
                return
            
            # Check if this is internal dialogue and hasn't been used yet
            if (turn.message.author.role == "tool" or
                    turn.message.content.content_type in [
                        "user_editable_context", "model_editable_context", 
                        "thoughts", "reasoning_recap"
                    ]):
                
                # Skip if this turn has already been used
                if turn_id in used_internal_turn_ids:
                    print(f"DEBUG: Skipping already used internal turn {turn_id}")
                    return
                
                internal_block = self._create_internal_dialogue_block(turn_id, turn.message)
                if internal_block:
                    internal_blocks.append(internal_block)
                    used_internal_turn_ids.add(turn_id)  # Mark as used
                    print(f"DEBUG: Added internal block {turn_id} to used set")
            
            # Continue traversing children
            for child_id in turn.children:
                traverse_subtree(child_id)
        
        # Start traversal from the parent turn's children
        for child_id in parent_turn.children:
            traverse_subtree(child_id)
        
        return internal_blocks
    
    def _create_internal_dialogue_block(self, turn_id: str, message: Message) -> Optional[Dict[str, Any]]:
        """Create an internal dialogue block for window-shading."""
        if not message.content:
            return None
        
        content_text = self._get_content_text(message)
        if not content_text.strip():
            return None
        
        # Determine the role label based on content type and metadata
        role_label = "Assistant"
        metadata = message.metadata or {}
        author_metadata = message.author.metadata or {}
        
        if message.author.role == "tool":
            role_label = "Tool"
        elif message.content.content_type == "thoughts":
            role_label = "Thoughts"
        elif message.content.content_type == "reasoning_recap":
            role_label = "Reasoning"
        elif message.content.content_type == "code":
            role_label = "Code"
        elif author_metadata.get('real_author', '').startswith('tool:'):
            role_label = "Tool Response"
        elif message.content.url:
            role_label = "Website"
        elif message.content.domain:
            role_label = "Search Result"
        
        # Get timestamp if available
        timestamp = None
        if message.create_time:
            timestamp = datetime.fromtimestamp(message.create_time)
        
        # Collect additional metadata
        additional_info = {}
        if message.content.url:
            additional_info['url'] = message.content.url
        if message.content.domain:
            additional_info['domain'] = message.content.domain
        if message.content.title:
            additional_info['title'] = message.content.title
        if author_metadata.get('real_author'):
            additional_info['real_author'] = author_metadata['real_author']
        if author_metadata.get('source'):
            additional_info['source'] = author_metadata['source']
        if metadata.get('is_visually_hidden_from_conversation'):
            additional_info['visually_hidden'] = metadata['is_visually_hidden_from_conversation']
        
        return {
            'block_type': 'internal_dialogue',
            'turn_id': turn_id,
            'role': role_label.lower(),
            'content': content_text,
            'timestamp': timestamp,
            'content_type': message.content.content_type or 'text',
            'additional_info': additional_info
        }

    def _should_skip_turn(self, message: Message) -> bool:
        """Check if a turn should be skipped (internal processing)."""
        if not message.content:
            return True
        
        content = message.content
        metadata = message.metadata or {}
        
        # Skip system messages (empty or internal)
        if message.author.role == "system":
            return True
        
        # Skip internal content types
        content_type = content.content_type or "text"
        skip_types = [
            "model_editable_context",
            "thoughts", 
            "reasoning_recap"
            # Note: user_editable_context and tool messages will be handled as window shades
        ]
        
        if content_type in skip_types:
            return True
        
        # Skip visually hidden messages
        if metadata.get('is_visually_hidden_from_conversation', False):
            return True
        
        # Skip empty content
        if not content.text and not content.parts:
            return True
        
        return False

    def _create_content_block(self, turn_id: str, message: Message, timestamp: Optional[datetime]) -> Optional[Dict[str, Any]]:
        """Create a content block from a message."""
        
        print(f"DEBUG: Creating content block for turn {turn_id} - role: {message.author.role}")
        
        # Handle conversation context messages (these should be in a separate section)
        if self._is_conversation_context_message(message):
            print(f"DEBUG: Turn {turn_id} is conversation context")
            return self._create_conversation_context_block(turn_id, message, timestamp)
        
        # Handle tool messages
        if message.author.role == "tool" or self._is_tool_message(message):
            print(f"DEBUG: Turn {turn_id} is tool message")
            return self._create_tool_block(turn_id, message, timestamp)
        
        # Handle different content types
        content_type = message.content.content_type or "text"
        print(f"DEBUG: Turn {turn_id} content_type: {content_type}")
        
        if content_type == "text":
            block = self._create_text_block(turn_id, message, timestamp)
            print(f"DEBUG: Created text block for {turn_id}: {block is not None}")
            return block
        elif content_type == "code":
            block = self._create_code_block(turn_id, message, timestamp)
            print(f"DEBUG: Created code block for {turn_id}: {block is not None}")
            return block
        else:
            # Default to text block for unknown types
            block = self._create_text_block(turn_id, message, timestamp)
            print(f"DEBUG: Created default text block for {turn_id}: {block is not None}")
            return block

    def _is_conversation_context_message(self, message: Message) -> bool:
        """Check if message contains conversation context."""
        if not message.content:
            return False
        
        content = message.content
        metadata = message.metadata or {}
        
        print(f"DEBUG: Checking conversation context for turn {message.id} - role: {message.author.role}")
        print(f"DEBUG: is_visually_hidden_from_conversation: {metadata.get('is_visually_hidden_from_conversation', False)}")
        print(f"DEBUG: is_user_system_message: {metadata.get('is_user_system_message', False)}")
        print(f"DEBUG: has user_context_message_data: {bool(metadata.get('user_context_message_data'))}")
        
        # Check if this message is visually hidden from conversation
        if metadata.get('is_visually_hidden_from_conversation', False):
            print("DEBUG: Marking as context - visually hidden")
            return True
        
        # Check if this is explicitly marked as a system message
        if metadata.get('is_user_system_message', False):
            print("DEBUG: Marking as context - user system message")
            return True
        
        # Check if this is a context message with specific context data
        if metadata.get('user_context_message_data'):
            print("DEBUG: Marking as context - has user context data")
            return True
        
        # Check if this is a pure context message (no actual conversation content)
        if content.user_profile and not content.text and not content.parts:
            print("DEBUG: Marking as context - pure user profile")
            return True
        
        if content.user_instructions and not content.text and not content.parts:
            print("DEBUG: Marking as context - pure user instructions")
            return True
        
        # If the message has actual conversation content (text or parts), 
        # it's not just context, even if it also has profile/instructions
        if content.text or content.parts:
            print("DEBUG: Marking as conversation - has actual content")
            return False
        
        print("DEBUG: Marking as context - default case")
        return False

    def _is_tool_message(self, message: Message) -> bool:
        """Check if message is a tool call."""
        metadata = message.metadata or {}
        return (
            message.author.role == "assistant" and 
            metadata.get('real_author', '').startswith('tool:')
        )

    def _create_conversation_context_block(self, turn_id: str, message: Message, timestamp: Optional[datetime]) -> Dict[str, Any]:
        """Create a conversation context block."""
        content = message.content
        metadata = message.metadata or {}
        
        # Extract user context data
        user_profile = _normalize_text(content.user_profile or "")
        user_instructions = _normalize_text(content.user_instructions or "")
        
        context_data = metadata.get('user_context_message_data', {})
        about_user = _normalize_text(context_data.get('about_user_message', ''))
        about_model = _normalize_text(context_data.get('about_model_message', ''))
        
        # Build context content
        context_parts = []
        if user_profile:
            context_parts.append(f"User Profile:\n{user_profile}")
        if about_user:
            context_parts.append(f"About User:\n{about_user}")
        if about_model:
            context_parts.append(f"About Model:\n{about_model}")
        if user_instructions:
            context_parts.append(f"User Instructions:\n{user_instructions}")
        
        context_content = "\n\n".join(context_parts)
        
        return {
            'block_id': turn_id,
            'author': "user",
            'role': "user",
            'timestamp': timestamp,
            'content': context_content,
            'block_type': "conversation_context",
            'metadata': {
                'user_profile': user_profile,
                'user_instructions': user_instructions,
                'about_user': about_user,
                'about_model': about_model
            }
        }

    def _create_tool_block(self, turn_id: str, message: Message, timestamp: Optional[datetime]) -> Dict[str, Any]:
        """Create a tool block."""
        metadata = message.metadata or {}
        
        tool_name = metadata.get('tool_name', 'unknown_tool')
        tool_input = metadata.get('tool_input', {})
        tool_output = metadata.get('tool_output', {})
        
        # Get content from message
        content_text = ""
        if message.content:
            if message.content.text:
                content_text = _normalize_text(message.content.text)
            elif message.content.parts:
                content_text = _normalize_text(" ".join(str(part) for part in message.content.parts))
        
        return {
            'block_id': turn_id,
            'author': "tool",
            'role': "tool",
            'timestamp': timestamp,
            'content': content_text,
            'block_type': "tool_call",
            'tool_name': tool_name,
            'input_data': str(tool_input),
            'output_data': str(tool_output),
            'metadata': metadata
        }

    def _create_text_block(self, turn_id: str, message: Message, timestamp: Optional[datetime]) -> Dict[str, Any]:
        """Create a text block."""
        content = message.content
        
        # Extract text content
        text_content = ""
        if content.text:
            text_content = _normalize_text(content.text)
        elif content.parts:
            text_content = _normalize_text(" ".join(str(part) for part in content.parts))
        
        print(f"DEBUG: Text block for {turn_id} - role: {message.author.role} - content length: {len(text_content)}")
        if len(text_content) < 100:  # Only show short content to avoid spam
            print(f"DEBUG: Text content: '{text_content}'")
        
        # Extract citations
        citations = []
        metadata = message.metadata or {}
        if metadata.get('citations'):
            citations = metadata['citations']
        
        return {
            'block_id': turn_id,
            'author': message.author.role,
            'role': message.author.role,
            'timestamp': timestamp,
            'content': text_content,
            'block_type': "text",
            'citations': citations,
            'metadata': metadata
        }

    def _create_code_block(self, turn_id: str, message: Message, timestamp: Optional[datetime]) -> Dict[str, Any]:
        """Create a code block."""
        content = message.content
        
        # Extract code content
        code_content = ""
        if content.text:
            code_content = _normalize_text(content.text)
        elif content.parts:
            code_content = _normalize_text(" ".join(str(part) for part in content.parts))
        
        return {
            'block_id': turn_id,
            'author': message.author.role,
            'role': message.author.role,
            'timestamp': timestamp,
            'content': code_content,
            'block_type': "code",
            'language': content.language,
            'metadata': message.metadata or {}
        }

    def _create_contextual_block(self, turn_id: str, message: Message, timestamp: Optional[datetime]) -> Dict[str, Any]:
        """Create a contextual block for special content types."""
        content = message.content
        metadata = message.metadata or {}
        
        # Build contextual content
        context_parts = []
        context_parts.append(f"**MessageContent Type:** {content.content_type}")
        
        # Add specific content based on type
        if content.content_type == "model_editable_context":
            if content.model_set_context:
                context_parts.append(f"**Model Context:**\n{content.model_set_context}")
            if content.repository:
                context_parts.append(f"**Repository:**\n{content.repository}")
            if content.repo_summary:
                context_parts.append(f"**Repository Summary:**\n{content.repo_summary}")
            if content.structured_context:
                context_parts.append(f"**Structured Context:**\n{content.structured_context}")
        
        elif content.content_type == "thoughts":
            if content.thoughts:
                context_parts.append(f"**Thoughts:**\n{content.thoughts}")
        
        elif content.content_type == "reasoning_recap":
            if content.content:
                context_parts.append(f"**Reasoning:**\n{content.content}")
        
        # Add any text content
        if content.text:
            context_parts.append(f"**MessageContent:**\n{content.text}")
        
        context_content = "\n\n".join(context_parts)
        
        return {
            'block_id': turn_id,
            'author': message.author.role,
            'role': message.author.role,
            'timestamp': timestamp,
            'content': context_content,
            'block_type': "contextual",
            'metadata': metadata
        } 