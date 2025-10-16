#!/usr/bin/env python3
"""
Turn Processor V2 - Uses parent-child traversal for correct conversation flow.
"""
import logging
from typing import Any, Dict, List, Optional

from extract_chat.context.document_context import DocumentContext
from extract_chat.processors.reference_processing.citation_processor import (
    CitationProcessor,
)

logger = logging.getLogger(__name__)


class TurnProcessorV2:
    """Processes conversations using parent-child traversal for correct flow."""

    def __init__(self):
        """Initialize the turn processor."""
        self.processed_blocks = []
        self.internal_dialogue_groups = {}  # Group internal turns by request_id
        self.reference_turn_counter = 0  # Track turns with references
        self.global_reference_seq = 1
        self.reference_seq_map: Dict[tuple, int] = {}

    def process_conversation(self, conversation: Any) -> List[Dict[str, Any]]:
        """Process conversation using parent-child traversal."""
        logger.info("Processing conversation with parent-child traversal...")

        # Find root turns (those with no parent or parent is None)
        mapping = conversation.mapping
        dc = DocumentContext.get()
        if dc:
            root_turns = dc.get_root_turn_ids()
        else:
            root_turns = []
            for turn_id, turn_data in mapping.items():
                parent = getattr(turn_data, 'parent', None)
                if parent is None:
                    root_turns.append(turn_id)

        logger.info(f"Found {len(root_turns)} root turns: {root_turns}")

        # Process each root turn and its children
        all_blocks = []
        visited = set()

        for root_id in root_turns:
            blocks = self._traverse_turn(mapping, root_id, visited)
            all_blocks.extend(blocks)

        # Group internal dialogue with assistant responses
        final_blocks = self._attach_internal_dialogue_to_assistant(all_blocks)

        logger.info(f"Processed {len(final_blocks)} blocks total")
        return final_blocks

    def _traverse_turn(self, mapping: Dict[str, Any], turn_id: str, visited: set, level: int = 0) -> List[Dict[str, Any]]:
        """Traverse a turn and its children recursively."""
        if turn_id in visited:
            return []

        visited.add(turn_id)
        turn_data = mapping.get(turn_id)
        if not turn_data:
            return []

        blocks = []

        # Process this turn
        turn_block = self._process_single_turn(turn_data, turn_id, level)
        if turn_block:
            blocks.append(turn_block)

        # Process children in order
        children = getattr(turn_data, 'children', [])
        for child_id in children:
            child_blocks = self._traverse_turn(mapping, child_id, visited, level + 1)
            blocks.extend(child_blocks)

        return blocks

    def _process_single_turn(self, turn_data: Any, turn_id: str, level: int) -> Optional[Dict[str, Any]]:
        """Process a single turn and determine its type."""
        message = getattr(turn_data, 'message', None)
        if not message:
            # Turn with no message - structural turn, skip it
            return None

        # Extract basic information
        author = getattr(message, 'author', {})
        role = getattr(author, 'role', 'unknown') if author else 'unknown'
        content = getattr(message, 'content', {})
        metadata = getattr(message, 'metadata', {})

        # Note: We don't filter out turns based on is_visually_hidden_from_conversation
        # as this is not a reliable indicator of whether a turn should appear in output

        # Determine turn type based on content and metadata
        turn_type = self._determine_turn_type(message, role, content, metadata)

        # Create appropriate block based on type
        if turn_type == 'conversation_context':
            return self._create_conversation_context_block(message, turn_id, level)
        elif turn_type == 'user':
            return self._create_user_block(message, turn_id, level)
        elif turn_type == 'assistant':
            return self._create_assistant_block(message, turn_id, level, turn_data)
        elif turn_type == 'tool':
            return self._create_tool_block(message, turn_id, level)
        elif turn_type == 'system':
            return self._create_system_block(message, turn_id, level)
        elif turn_type == 'internal_dialogue':
            return self._create_internal_dialogue_block(message, turn_id, level)
        else:
            return self._create_unknown_block(message, turn_id, level)

    def _determine_turn_type(self, message: Any, role: str, content: Any, metadata: Any) -> str:
        """Determine the type of turn based on its characteristics."""

        # Check for conversation context - use the most reliable indicator
        is_user_system = getattr(metadata, 'is_user_system_message', False)
        if is_user_system:
            try:
                if DocumentContext.get() and DocumentContext.get().is_verbose():
                    logging.getLogger(__name__).debug("Found is_user_system_message for turn")
            except Exception:
                pass
            return 'conversation_context'

        # Debug: Check if metadata has the field but getattr is not working
        if hasattr(metadata, '__getitem__'):
            is_user_system_dict = metadata.get('is_user_system_message', False)
            if is_user_system_dict:
                try:
                    if DocumentContext.get() and DocumentContext.get().is_verbose():
                        logging.getLogger(__name__).debug("Found is_user_system_message via dict access")
                except Exception:
                    pass
                return 'conversation_context'

        # Check for internal dialogue indicators
        if self._is_internal_dialogue(message, role, content, metadata):
            return 'internal_dialogue'

        # Determine by role - this should be the primary classifier
        if role == 'user':
            return 'user'
        elif role == 'assistant':
            return 'assistant'
        elif role == 'tool':
            return 'tool'
        elif role == 'system':
            return 'system'
        else:
            return 'unknown'

    def _is_internal_dialogue(self, message: Any, role: str, content: Any, metadata: Any) -> bool:
        """Determine if a turn is internal dialogue that should be window-shaded."""
        content_type = getattr(content, 'content_type', None)

        # Internal dialogue content types
        internal_content_types = [
            'model_editable_context',
            'thoughts',
            'reasoning_recap',  # Added reasoning_recap
            'code'  # Tool calls and internal code
        ]

        if content_type in internal_content_types:
            return True

        # Check for tool calls with specific patterns
        if content_type == 'code':
            text = getattr(content, 'text', '')
            if text in ['search()', 'browse()'] or text.startswith('{"search_query"'):
                return True

        # Check for real_author indicating tool processing
        author_metadata = getattr(getattr(message, 'author', {}), 'metadata', {})
        real_author = author_metadata.get('real_author', '')
        if real_author.startswith('tool:'):
            return True

        # Check for user turns that are part of internal dialogue (have system_hints)
        if role == 'user' and metadata:
            # Try both getattr and direct access for system_hints
            system_hints = getattr(metadata, 'system_hints', None)
            if not system_hints and hasattr(metadata, '__getitem__'):
                system_hints = metadata.get('system_hints', None)
            if system_hints:
                return True

        return False

    def _group_internal_dialogue(self, blocks: List[Dict[str, Any]]) -> None:
        """Group internal dialogue blocks by request_id."""
        self.internal_dialogue_groups = {}

        for block in blocks:
            if block.get('type') == 'internal_dialogue':
                request_id = block.get('metadata', {}).get('request_id')
                if request_id:
                    if request_id not in self.internal_dialogue_groups:
                        self.internal_dialogue_groups[request_id] = []
                    self.internal_dialogue_groups[request_id].append(block)

    def _replace_with_grouped_internal_dialogue(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Replace individual internal dialogue blocks with grouped blocks."""
        final_blocks = []
        processed_internal_ids = set()

        for block in blocks:
            if block.get('type') == 'internal_dialogue':
                request_id = block.get('metadata', {}).get('request_id')
                if request_id and request_id not in processed_internal_ids:
                    # Create grouped internal dialogue block
                    grouped_block = self._create_grouped_internal_dialogue_block(request_id)
                    if grouped_block:
                        final_blocks.append(grouped_block)
                        processed_internal_ids.add(request_id)
            else:
                final_blocks.append(block)

        return final_blocks

    def _create_grouped_internal_dialogue_block(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Create a grouped internal dialogue block for a specific request_id."""
        internal_blocks = self.internal_dialogue_groups.get(request_id, [])
        if not internal_blocks:
            return None

        # Sort internal blocks by timestamp
        internal_blocks.sort(key=lambda x: x.get('metadata', {}).get('timestamp', 0))

        return {
            'type': 'grouped_internal_dialogue',
            'level': 0,
            'content': {
                'request_id': request_id,
                'internal_blocks': internal_blocks
            },
            'metadata': {
                'request_id': request_id,
                'block_count': len(internal_blocks),
                'first_timestamp': internal_blocks[0].get('metadata', {}).get('timestamp') if internal_blocks else None,
                'last_timestamp': internal_blocks[-1].get('metadata', {}).get('timestamp') if internal_blocks else None
            }
        }

    def _create_internal_dialogue_block(self, message: Any, turn_id: str, level: int) -> Dict[str, Any]:
        """Create an internal dialogue block."""
        content = getattr(message, 'content', {})
        metadata = getattr(message, 'metadata', {})
        author = getattr(message, 'author', {})

        content_type = getattr(content, 'content_type', 'unknown')
        dc = DocumentContext.get()
        text_content = dc.extract_text_from_content(content) if dc else self._extract_text_content(content)

        return {
            'type': 'internal_dialogue',
            'level': level,
            'content': {
                'content_type': content_type,
                'text': text_content,
                'language': getattr(content, 'language', None),
                'thoughts': getattr(content, 'thoughts', []),
                'search_queries': metadata.get('search_queries', []),
                'search_result_groups': metadata.get('search_result_groups', [])
            },
            'metadata': {
                'turn_id': turn_id,
                'timestamp': getattr(message, 'create_time', None),
                'message_id': getattr(message, 'id', None),
                'request_id': metadata.get('request_id'),
                'author_role': getattr(author, 'role', 'unknown'),
                'real_author': getattr(author, 'metadata', {}).get('real_author'),
                'model_slug': metadata.get('model_slug'),
                'status': getattr(message, 'status', 'unknown')
            }
        }

    def _create_conversation_context_block(self, message: Any, turn_id: str, level: int) -> Dict[str, Any]:
        """Create a conversation context block."""
        content = getattr(message, 'content', {})
        metadata = getattr(message, 'metadata', {})

        # Extract context information from content
        user_profile = getattr(content, 'user_profile', None)
        user_instructions = getattr(content, 'user_instructions', None)

        # Extract context information from metadata - user_context_message_data is a Dict[str, Any]
        user_context_data = metadata.get('user_context_message_data', {}) if metadata else {}

        # Also check if user_context_message_data is a separate field on the message
        user_context_data_separate = getattr(message, 'user_context_message_data', None)

        # Use the separate field since that's where the data actually is
        user_context_data = user_context_data_separate or user_context_data

        about_user = user_context_data.get('about_user_message') if user_context_data else None
        about_model = user_context_data.get('about_model_message') if user_context_data else None

        return {
            'type': 'conversation_context',
            'level': level,
            'content': {
                'user_profile': user_profile,
                'user_instructions': user_instructions
            },
            'metadata': {
                'turn_id': turn_id,
                'timestamp': getattr(message, 'create_time', None),
                'message_id': getattr(message, 'id', None),
                'about_user': about_user,
                'about_model': about_model
            }
        }

    def _create_user_block(self, message: Any, turn_id: str, level: int) -> Dict[str, Any]:
        """Create a user message block."""
        content = getattr(message, 'content', {})
        text_content = self._extract_text_content(content)

        return {
            'type': 'user',
            'level': level,
            'content': text_content,
            'metadata': {
                'turn_id': turn_id,
                'timestamp': getattr(message, 'create_time', None),
                'message_id': getattr(message, 'id', None),
                'author': getattr(getattr(message, 'author', {}), 'role', 'user')
            }
        }

    def _create_assistant_block(self, message: Any, turn_id: str, level: int, turn_data: Any = None) -> Dict[str, Any]:
        """Create an assistant message block."""
        content = getattr(message, 'content', {})
        metadata = getattr(message, 'metadata', {})
        text_content = self._extract_text_content(content)

        # Check if this turn has references
        dc = DocumentContext.get()
        has_references = dc.has_references_in_message(message) if dc else self._has_references(message)
        if has_references:
            self.reference_turn_counter += 1

        block = {
            'type': 'assistant',
            'level': level,
            'content': text_content,
            'metadata': {
                'turn_id': turn_id,
                'timestamp': getattr(message, 'create_time', None),
                'message_id': getattr(message, 'id', None),
                'author': getattr(getattr(message, 'author', {}), 'role', 'assistant'),
                'model_slug': metadata.get('model_slug'),
                'recipient': getattr(message, 'recipient', None),
                'end_turn': metadata.get('end_turn'),
                'request_id': metadata.get('request_id'),
                'has_references': has_references,
                'reference_turn_number': self.reference_turn_counter if has_references else None
            }
        }

        # If this turn has references, process them and add the references table
        if has_references:
            citation_processor = CitationProcessor()
            reference_block, next_seq = citation_processor.get_references_data(
                turn=turn_data,
                ref_turn_counter=self.reference_turn_counter,
                start_seq=self.global_reference_seq,
                existing_sequences=self.reference_seq_map,
            )
            self.global_reference_seq = next_seq
            block['references_table'] = reference_block

        return block

    def _create_tool_block(self, message: Any, turn_id: str, level: int) -> Dict[str, Any]:
        """Create a tool message block."""
        content = getattr(message, 'content', {})
        dc = DocumentContext.get()
        text_content = dc.extract_text_from_content(content) if dc else self._extract_text_content(content)

        return {
            'type': 'tool',
            'level': level,
            'content': text_content,
            'metadata': {
                'turn_id': turn_id,
                'timestamp': getattr(message, 'create_time', None),
                'message_id': getattr(message, 'id', None),
                'author': getattr(getattr(message, 'author', {}), 'role', 'tool')
            }
        }

    def _create_system_block(self, message: Any, turn_id: str, level: int) -> Dict[str, Any]:
        """Create a system message block."""
        content = getattr(message, 'content', {})
        dc = DocumentContext.get()
        text_content = dc.extract_text_from_content(content) if dc else self._extract_text_content(content)

        return {
            'type': 'system',
            'level': level,
            'content': text_content,
            'metadata': {
                'turn_id': turn_id,
                'timestamp': getattr(message, 'create_time', None),
                'message_id': getattr(message, 'id', None),
                'author': getattr(getattr(message, 'author', {}), 'role', 'system')
            }
        }

    def _create_structural_block(self, turn_data: Any, turn_id: str, level: int) -> Dict[str, Any]:
        """Create a block for structural turns (no message)."""
        return {
            'type': 'structural',
            'level': level,
            'content': None,
            'metadata': {
                'turn_id': turn_id,
                'parent': getattr(turn_data, 'parent', None),
                'children': getattr(turn_data, 'children', [])
            }
        }

    def _create_unknown_block(self, message: Any, turn_id: str, level: int) -> Dict[str, Any]:
        """Create a block for unknown message types."""
        content = getattr(message, 'content', {})
        dc = DocumentContext.get()
        text_content = dc.extract_text_from_content(content) if dc else self._extract_text_content(content)

        return {
            'type': 'unknown',
            'level': level,
            'content': text_content,
            'metadata': {
                'turn_id': turn_id,
                'timestamp': getattr(message, 'create_time', None),
                'message_id': getattr(message, 'id', None),
                'author': getattr(getattr(message, 'author', {}), 'role', 'unknown')
            }
        }

    def _extract_text_content(self, content: Any) -> str:
        """Extract text content from message content."""
        if not content:
            return ""

        # Try different content fields
        text = getattr(content, 'text', None)
        if text:
            return str(text)

        parts = getattr(content, 'parts', None)
        if parts:
            # Join parts if they're strings
            if isinstance(parts, list):
                text_parts = [str(part) for part in parts if part]
                return "\n".join(text_parts)

        # Try other content fields
        for field in ['thoughts', 'model_set_context', 'repository', 'repo_summary']:
            value = getattr(content, field, None)
            if value:
                return str(value)

        return ""

    def _has_references(self, message: Any) -> bool:
        """Check if a turn has references: by metadata arrays OR inline markers in text."""
        if not message:
            return False
        # Metadata-based detection
        metadata = getattr(message, 'metadata', None)
        if metadata:
            try:
                citations = metadata.get('citations', [])
                if citations:
                    return True
            except Exception:
                pass
            try:
                content_refs = metadata.get('content_references', [])
                if content_refs:
                    return True
            except Exception:
                pass
        # Fallback: text-based detection
        try:
            content = getattr(message, 'content', None)
            text = ''
            if hasattr(content, 'text') and content.text:
                text = str(content.text)
            elif hasattr(content, 'parts') and isinstance(content.parts, list):
                text = "\n".join(str(p) for p in content.parts if p)
            elif isinstance(content, str):
                text = content
            if text:
                import re as _re
                if _re.search(r'【\d+†L\d+-L\d+】', text):
                    return True
        except Exception:
            pass
        return False

    def _attach_internal_dialogue_to_assistant(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process blocks in sequence, maintaining state between internal dialogue and visible conversation."""
        final_blocks = []
        current_internal_dialogue = []
        in_internal_mode = False

        for block in blocks:
            # Determine if this block is visible (external dialogue) or internal
            is_visible = self._is_visible_turn(block)

            if not is_visible:
                # This is internal dialogue - add to current internal dialogue group
                if not in_internal_mode:
                    # Starting internal dialogue mode
                    in_internal_mode = True
                    current_internal_dialogue = []

                # Convert any non-internal_dialogue blocks to internal_dialogue format
                if block.get('type') != 'internal_dialogue':
                    internal_block = self._convert_to_internal_dialogue(block)
                    current_internal_dialogue.append(internal_block)
                else:
                    # Already in internal_dialogue format
                    current_internal_dialogue.append(block)

            elif is_visible and in_internal_mode:
                # We're transitioning from internal dialogue to visible conversation
                # Attach the accumulated internal dialogue to this visible block
                if current_internal_dialogue:
                    block['internal_dialogue'] = current_internal_dialogue
                    current_internal_dialogue = []
                in_internal_mode = False
                final_blocks.append(block)

            elif is_visible:
                # We're in visible conversation mode
                final_blocks.append(block)

            else:
                # Unknown block type, treat as visible
                final_blocks.append(block)

        # If we end in internal dialogue mode, add the remaining internal dialogue as a separate block
        if in_internal_mode and current_internal_dialogue:
            final_blocks.extend(current_internal_dialogue)

        return final_blocks

    def _is_visible_turn(self, block: Dict[str, Any]) -> bool:
        """Determine if a turn is visible (external dialogue) or internal."""
        block_type = block.get('type')
        metadata = block.get('metadata', {})

        # Special case: conversation_context blocks are always visible
        if block_type == 'conversation_context':
            return True

        # Check for system_hints - this indicates internal communication
        if metadata.get('system_hints'):
            return False

        # Check for real_author starting with 'tool:' - this is internal tool communication
        real_author = metadata.get('real_author', '')
        if real_author and real_author.startswith('tool:'):
            return False

        # Check for model_slug indicating internal processing (e.g., "research")
        model_slug = metadata.get('model_slug', '')
        if model_slug and model_slug != 'gpt-4-5' and model_slug != 'gpt-4':
            return False

        # Check for specific recipient indicating internal tool communication
        recipient = metadata.get('recipient', '')
        if recipient and recipient != 'all' and 'tool' in recipient.lower():
            return False

        # Check for end_turn being false (internal turns often don't end the conversation)
        end_turn = metadata.get('end_turn')
        if end_turn is False:
            return False

        # Check content types that indicate internal processing
        content = block.get('content', {})
        if isinstance(content, dict):
            content_type = content.get('content_type', '')
            if content_type in ['model_editable_context', 'thoughts', 'reasoning_recap', 'code']:
                return False

        # Check for specific internal dialogue types
        if block_type == 'internal_dialogue':
            return False

        # For tool blocks, check if they're part of internal processing
        if block_type == 'tool':
            # Tool blocks with empty content or specific metadata are internal
            if not content or content == "":
                return False
            # Tool blocks with async_task metadata are internal
            if metadata.get('async_task_type') or metadata.get('async_task_id'):
                return False

        # Default to visible for user, assistant, system blocks
        # unless they have other indicators of being internal
        return True

    def _convert_to_internal_dialogue(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a block to internal_dialogue format."""
        return {
            'type': 'internal_dialogue',
            'level': block.get('level', 0),
            'content': {
                'content_type': 'text',
                'text': block.get('content', '')
            },
            'metadata': {
                'turn_id': block.get('metadata', {}).get('turn_id'),
                'timestamp': block.get('metadata', {}).get('timestamp'),
                'message_id': block.get('metadata', {}).get('message_id'),
                'request_id': block.get('metadata', {}).get('request_id'),
                'author_role': block.get('metadata', {}).get('author_role', 'unknown'),
                'real_author': block.get('metadata', {}).get('real_author'),
                'model_slug': block.get('metadata', {}).get('model_slug'),
                'status': block.get('metadata', {}).get('status', 'finished_successfully')
            }
        }
