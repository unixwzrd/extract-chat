"""
ChatGPT conversation schema definitions.

This module provides comprehensive Pydantic models for parsing and validating
ChatGPT conversation JSON data, including all metadata fields and nested structures.
"""

from .conversation import (Conversation, Message, MessageAuthor,
                           MessageContent, Turn)
from .metadata import (  # Plugin and tool structures; Search and citation structures
    AdaVisualization, AggregateResult, AppPairing, AsyncTaskStatusMessages,
    Attachment, AudioAssetPointer, Canvas, Citation, CitationFormat,
    CitationMetadata, CiteMetadata, ContentPart, ContentReference,
    ContentThought, ContentWorkspace, FinishDetails, ImageResult,
    InvokedPlugin, JitPluginData, ModelSwitcherDeny, ParagenVariantsInfo,
    Permission, SearchQuery, SearchResultGroup, SerializationMetadata,
    SonicClassificationResult, UserContextMessageData)

__all__ = [
    # Base conversation models
    'MessageAuthor',
    'MessageContent', 
    'Message',
    'Turn',
    'Conversation',
    
    # Metadata models
    'JitPluginData',
    'InvokedPlugin',
    'SearchResultGroup',
    'Citation',
    'ContentReference',
    'AggregateResult',
    'Canvas',
    'ContentPart',
    'Attachment',
    'ImageResult',
    'AsyncTaskStatusMessages',
    'UserContextMessageData',
    'ModelSwitcherDeny',
    'ParagenVariantsInfo',
    'SerializationMetadata',
    'SonicClassificationResult',
    'FinishDetails',
    'Permission',
    'SearchQuery',
    'CitationMetadata',
    'CitationFormat',
    'CiteMetadata',
    'AdaVisualization',
    'AppPairing',
    'AudioAssetPointer',
    'ContentThought',
    'ContentWorkspace'
] 
