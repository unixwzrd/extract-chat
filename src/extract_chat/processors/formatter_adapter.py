"""
Formatter adapter for conversation processing.

This module provides an adapter that takes processed blocks and provides
the interface that formatters expect.
"""

from typing import Any, Dict, List


class FormatterAdapter:
    """Adapter for processed conversation blocks to provide formatter interface."""
    
    def __init__(self, blocks: List[Dict[str, Any]], original_conversation: Any = None):
        """
        Initialize the wrapper.
        
        Args:
            blocks: List of processed blocks from TurnProcessor
            original_conversation: Original conversation object for metadata
        """
        self.blocks = blocks
        self.original_conversation = original_conversation
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the conversation, behaving like a dictionary.
        
        Args:
            key: The key to get
            default: Default value if key not found
            
        Returns:
            The value for the key
        """
        if key == 'content_blocks':
            return self.blocks
        elif key == 'title':
            return getattr(self.original_conversation, 'title', None) if self.original_conversation else None
        elif key == 'conversation_id':
            return getattr(self.original_conversation, 'conversation_id', None) if self.original_conversation else None
        elif key == 'create_time':
            return getattr(self.original_conversation, 'create_time', None) if self.original_conversation else None
        elif key == 'update_time':
            return getattr(self.original_conversation, 'update_time', None) if self.original_conversation else None
        elif key == 'default_model_slug':
            return getattr(self.original_conversation, 'default_model_slug', None) if self.original_conversation else None
        elif key == 'original_conversation':
            return self.original_conversation
        else:
            return default
    
    def __getitem__(self, key: str) -> Any:
        """
        Support dictionary-style access.
        
        Args:
            key: The key to get
            
        Returns:
            The value for the key
            
        Raises:
            KeyError: If key not found
        """
        value = self.get(key)
        if value is None and key not in ['content_blocks', 'title', 'conversation_id', 'create_time', 'update_time', 'default_model_slug']:
            raise KeyError(key)
        return value
    
    def get_content_blocks(self) -> List[Dict[str, Any]]:
        """
        Get content blocks for the formatter.
        
        Returns:
            List of content blocks
        """
        return self.blocks
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get conversation metadata.
        
        Returns:
            Dictionary of metadata
        """
        if not self.original_conversation:
            return {}
        
        return {
            'title': getattr(self.original_conversation, 'title', None),
            'create_time': getattr(self.original_conversation, 'create_time', None),
            'update_time': getattr(self.original_conversation, 'update_time', None),
            'conversation_id': getattr(self.original_conversation, 'conversation_id', None),
            'default_model_slug': getattr(self.original_conversation, 'default_model_slug', None)
        } 