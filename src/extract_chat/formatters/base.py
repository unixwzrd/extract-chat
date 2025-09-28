"""
Base formatter interface for extract_chat.

This module defines the base classes and interfaces for all output formatters.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import ftfy


# Note: Avoid importing Conversation here to keep formatter base decoupled
class BaseFormatter(ABC):
    """
    Base class for all output formatters.

    This class defines the interface that all formatters must implement.
    Formatters convert the intermediate representation to specific output formats.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the formatter with optional configuration.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    @abstractmethod
    def format_document(self, document: Any) -> str:
        """
        Format a document to the target output format.

        Args:
            document: The conversation to format

        Returns:
            Formatted output as a string
        """
        pass

    @abstractmethod
    def format_conversation(self, conversation: Any) -> str:
        """
        Format a conversation to the target output format.

        Args:
            conversation: The conversation to format

        Returns:
            Formatted output as a string
        """
        pass

    def validate_document(self, document: Any) -> bool:
        """
        Validate that the document can be formatted.

        Args:
            document: The ChatGPT conversation to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Accept either a Conversation (has mapping) or a FormatterAdapter
            # (has get_content_blocks/get_metadata)
            if not document:
                return False
            if hasattr(document, 'mapping'):
                return True
            if hasattr(document, 'get_content_blocks') and hasattr(document, 'get_metadata'):
                return True
            return False
        except Exception as e:
            # Log validation errors for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Document validation error: {e}")
            return False

    def get_supported_features(self) -> Dict[str, bool]:
        """
        Get information about supported features.

        Returns:
            Dictionary mapping feature names to support status
        """
        return {
            'citations': True,
            'code_blocks': True,
            'tool_calls': True,
            'user_context': True,
            'assets': True,
            'metadata': True,
        }

    def get_format_info(self) -> Dict[str, Any]:
        """
        Get information about the output format.

        Returns:
            Dictionary with format information
        """
        return {
            'name': self.__class__.__name__,
            'description': self.__class__.__doc__ or '',
            'file_extension': self.get_file_extension(),
            'mime_type': self.get_mime_type(),
        }

    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get the file extension for this format.

        Returns:
            File extension (e.g., '.md', '.html', '.txt')
        """
        pass

    @abstractmethod
    def get_mime_type(self) -> str:
        """
        Get the MIME type for this format.

        Returns:
            MIME type (e.g., 'text/markdown', 'text/html', 'text/plain')
        """
        pass

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text content for consistent formatting.
        
        This is a shared method that both Markdown and HTML formatters can use
        to ensure consistent text processing.
        
        Args:
            text: Raw text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Use more aggressive Unicode normalization
        try:
            text = ftfy.fix_text(
                text, 
                normalization='NFKC', 
                fix_character_width=True, 
                fix_latin_ligatures=True
            )
        except ImportError:
            # Fallback if ftfy is not available
            pass
        
        
        # Additional Unicode cleanup for problematic characters

        # Remove or replace problematic Unicode characters
        # Replace citation markers and other unprintable characters
        text = re.sub(r'[^\x00-\x7F\u00A0-\uFFFF]', '', text)
        
        # Remove specific problematic Unicode ranges
        text = re.sub(r'[\uE000-\uF8FF]', '', text)  # Private Use Area
        text = re.sub(r'[\uFFF0-\uFFFF]', '', text)  # Specials
        
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Note: Triple backticks are handled specifically in conversation context formatting
        
        # Remove excessive whitespace while preserving intentional formatting
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            # Preserve intentional indentation but normalize excessive spaces
            stripped = line.rstrip()
            if stripped:
                normalized_lines.append(stripped)
            else:
                # Keep empty lines but limit consecutive empty lines
                if not normalized_lines or normalized_lines[-1]:
                    normalized_lines.append("")
        
        return '\n'.join(normalized_lines)

    def _fix_triple_backticks(self, text: str) -> str:
        """
        Fix triple backticks formatting to ensure proper spacing.
        
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
                # This is a backtick block (odd indices)
                # Add newline before if missing
                if not part.startswith('\n') and not part.startswith(' '):
                    part = '\n' + part
                
                # Add newline after if missing
                if not part.endswith('\n'):
                    part = part + '\n'
                
                result_parts.append('```' + part + '```')
            else:
                # This is content between backtick blocks (even indices)
                result_parts.append(part)
        
        return ''.join(result_parts)

    def _format_timestamp(self, timestamp) -> str:
        """
        Format timestamp consistently across formatters.
        
        Args:
            timestamp: Timestamp to format
            
        Returns:
            Formatted timestamp string
        """
        if not timestamp:
            return ""
        
        try:
            return timestamp.strftime('%Y-%m-%d %H:%M:%S')
        except (AttributeError, TypeError):
            return str(timestamp)

    def _extract_conversation_context_data(self, block: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract conversation context data from a block.
        
        This is a shared method that both Markdown and HTML formatters can use
        to extract the same context data consistently.
        
        Args:
            block: Content block dictionary
            
        Returns:
            Dictionary with extracted context data
        """
        metadata = block.get('metadata', {})
        return {
            'user_profile': metadata.get('user_profile', ''),
            'user_instructions': metadata.get('user_instructions', ''),
            'about_user': metadata.get('about_user', ''),
            'about_model': metadata.get('about_model', '')
        }


class FormatterError(Exception):
    """Base exception for formatter errors."""

    def __init__(self, message: str, formatter: Optional[BaseFormatter] = None):
        super().__init__(message)
        self.formatter = formatter


class ValidationError(FormatterError):
    """Exception raised when document validation fails."""
    pass


class FormattingError(FormatterError):
    """Exception raised when formatting fails."""
    pass 
