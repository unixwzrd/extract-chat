"""
ChatGPT metadata schema.

This module contains all the nested metadata structures found in ChatGPT conversations,
organized by logical groups for better maintainability.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

# ============================================================================
# PLUGIN AND TOOL STRUCTURES
# ============================================================================

class JitPluginActionAllow(BaseModel):
    """JIT plugin action allow structure."""
    target_message_id: str

    class Config:
        extra = "allow"


class JitPluginAction(BaseModel):
    """JIT plugin action structure."""
    allow: Optional[JitPluginActionAllow] = None
    name: str
    type: str

    class Config:
        extra = "allow"


class JitPluginBody(BaseModel):
    """JIT plugin body structure."""
    actions: Optional[List[JitPluginAction]] = None
    domain: str
    is_consequential: bool
    method: str
    operation: str
    params: Optional[Dict[str, Any]] = None
    path: str
    privacy_policy: str

    class Config:
        extra = "allow"


class JitPluginFromServer(BaseModel):
    """JIT plugin from server structure."""
    body: JitPluginBody
    type: str

    class Config:
        extra = "allow"


class JitPluginFromClientUserAction(BaseModel):
    """JIT plugin from client user action structure."""
    data: Dict[str, Any]
    target_message_id: str

    class Config:
        extra = "allow"


class JitPluginFromClient(BaseModel):
    """JIT plugin from client structure."""
    user_action: JitPluginFromClientUserAction

    class Config:
        extra = "allow"


class JitPluginData(BaseModel):
    """JIT plugin data structure."""
    from_client: Optional[JitPluginFromClient] = None
    from_server: Optional[JitPluginFromServer] = None

    class Config:
        extra = "allow"


class InvokedPlugin(BaseModel):
    """Invoked plugin structure."""
    http_response_status: int
    namespace: str
    plugin_id: str
    type: str

    class Config:
        extra = "allow"


# ============================================================================
# SEARCH AND CITATION STRUCTURES
# ============================================================================

class SearchQuery(BaseModel):
    """Search query structure."""
    q: str
    type: str

    class Config:
        extra = "allow"


class SearchResultGroupEntry(BaseModel):
    """Search result group entry structure."""
    attribution: str
    attributions: Optional[Any] = None
    attributions_debug: Optional[Any] = None
    content_type: Optional[str] = None
    pub_date: Optional[Union[float, int]] = None
    ref_id: Optional[Union[Dict[str, Any], None]] = None
    snippet: str
    title: str
    type: str
    url: str

    class Config:
        extra = "allow"


class SearchResultGroup(BaseModel):
    """Search result group structure."""
    domain: str
    entries: List[SearchResultGroupEntry]
    type: str

    class Config:
        extra = "allow"


class CitationMetadata(BaseModel):
    """Citation metadata structure."""
    extra: Optional[Dict[str, Any]] = None
    id: str
    name: str
    og_tags: Optional[Any] = None
    pub_date: Optional[str] = None
    source: str
    text: str
    title: str
    type: str
    url: str

    class Config:
        extra = "allow"


class CitationFormat(BaseModel):
    """Citation format structure."""
    name: str
    regex: str

    class Config:
        extra = "allow"


class CiteMetadata(BaseModel):
    """Cite metadata structure."""
    citation_format: CitationFormat
    metadata_list: List[CitationMetadata]
    original_query: Optional[str] = None

    class Config:
        extra = "allow"


class Citation(BaseModel):
    """Citation structure."""
    citation_format_type: str
    end_ix: int
    invalid_reason: str
    metadata: CitationMetadata
    start_ix: int

    class Config:
        extra = "allow"


# ============================================================================
# CONTENT REFERENCE STRUCTURES
# ============================================================================

class ContentReferenceBusinessFallback(BaseModel):
    """Content reference business fallback structure."""
    cite: str
    description: str
    location: str
    name: str
    ref_id: Optional[str] = None
    url: str

    class Config:
        extra = "allow"


class ContentReferenceBusinessHour(BaseModel):
    """Content reference business hour structure."""
    day: int
    end: str
    start: str

    class Config:
        extra = "allow"


class ContentReferenceBusiness(BaseModel):
    """Content reference business structure."""
    address: str
    categories: List[Union[str, List[str]]]
    description: str
    description_cite: str
    hours: List[ContentReferenceBusinessHour]
    id: str
    image_url: str
    image_urls: List[Union[str, List[str]]]
    is_closed_permanently: bool
    is_open: bool
    latitude: float
    longitude: float
    name: str
    next_open_hour: Optional[ContentReferenceBusinessHour] = None
    phone: str
    price: int
    price_str: Optional[str] = None
    provider: str
    provider_url: str
    rating: float
    rating_scale: int
    review_count: int
    website_url: str

    class Config:
        extra = "allow"


class ContentReferenceImage(BaseModel):
    """Content reference image structure."""
    attribution: str
    content_size: Dict[str, int]
    content_url: str
    thumbnail_crop_info: Optional[Any] = None
    thumbnail_size: Dict[str, int]
    thumbnail_url: str
    title: str
    url: str

    class Config:
        extra = "allow"


class ContentReferenceItemRef(BaseModel):
    """Content reference item ref structure."""
    ref_index: int
    ref_type: str
    turn_index: int

    class Config:
        extra = "allow"


class ContentReferenceItem(BaseModel):
    """Content reference item structure."""
    attribution: str
    attribution_segments: Optional[Any] = None
    attributions: Optional[Any] = None
    hue: Optional[Any] = None
    pub_date: Optional[Union[int, None]] = None
    refs: List[ContentReferenceItemRef]
    snippet: Optional[str] = None
    supporting_websites: List[Any]
    title: str
    url: str

    class Config:
        extra = "allow"


class ContentReferenceDomainSubDomain(BaseModel):
    """Content reference domain sub domain structure."""
    title: str
    url: str

    class Config:
        extra = "allow"


class ContentReferenceDomain(BaseModel):
    """Content reference domain structure."""
    attribution: str
    domain: str
    sub_domains: List[ContentReferenceDomainSubDomain]
    subtitle: str
    title: str
    url: str

    class Config:
        extra = "allow"


class ContentReference(BaseModel):
    """Content reference structure."""
    alt: Optional[str] = None
    attributable_index: str
    attribution: str
    attributions: Optional[Any] = None
    attributions_debug: Optional[Any] = None
    business_fallbacks: List[ContentReferenceBusinessFallback]
    businesses: List[ContentReferenceBusiness]
    cite_map: Dict[str, Any]
    cloud_doc_url: Optional[str] = None
    domains: List[ContentReferenceDomain]
    end_idx: int
    error: Optional[Any] = None
    fallback_items: Optional[Any] = None
    has_images: bool
    icon_type: Optional[Any] = None
    id: str
    images: List[ContentReferenceImage]
    invalid: bool
    items: List[ContentReferenceItem]
    matched_text: str
    name: str
    prompt_text: Optional[str] = None
    pub_date: Optional[Any] = None
    refs: List[Union[ContentReferenceItemRef, str, List[str]]]
    render_fallbacks: bool
    safe_urls: List[Union[str, List[str]]]
    snippet: str
    source: str
    sources: List[Any]
    start_idx: int
    status: str
    style: Optional[Any] = None
    title: str
    type: str
    url: str

    class Config:
        extra = "allow"


# ============================================================================
# EXECUTION AND RESULT STRUCTURES
# ============================================================================

class AggregateResultJupyterMessageParentHeader(BaseModel):
    """Aggregate result jupyter message parent header structure."""
    msg_id: str
    version: str

    class Config:
        extra = "allow"


class AggregateResultJupyterMessageContent(BaseModel):
    """Aggregate result jupyter message content structure."""
    execution_state: str

    class Config:
        extra = "allow"


class AggregateResultJupyterMessage(BaseModel):
    """Aggregate result jupyter message structure."""
    content: AggregateResultJupyterMessageContent
    msg_type: str
    parent_header: AggregateResultJupyterMessageParentHeader

    class Config:
        extra = "allow"


class AggregateResultMessage(BaseModel):
    """Aggregate result message structure."""
    height: int
    image_payload: Optional[Any] = None
    image_url: str
    message_type: str
    sender: str
    stream_name: str
    text: str
    time: float
    timeout_triggered: int
    width: int

    class Config:
        extra = "allow"


class AggregateResultException(BaseModel):
    """Aggregate result exception structure."""
    args: List[Union[str, List[str]]]
    name: str
    notes: List[Any]
    traceback: List[Union[str, List[str]]]

    class Config:
        extra = "allow"


class AggregateResult(BaseModel):
    """Aggregate result structure."""
    code: str
    end_time: Optional[float] = None
    final_expression_output: Optional[str] = None
    in_kernel_exception: Optional[AggregateResultException] = None
    jupyter_messages: List[AggregateResultJupyterMessage]
    messages: List[AggregateResultMessage]
    run_id: str
    start_time: float
    status: str
    system_exception: Optional[AggregateResultException] = None
    timeout_triggered: Optional[int] = None
    update_time: float

    class Config:
        extra = "allow"


class CanvasSelectionMetadataSelectionPositionRange(BaseModel):
    """Canvas selection metadata selection position range structure."""
    end: int
    start: int

    class Config:
        extra = "allow"


class CanvasSelectionMetadata(BaseModel):
    """Canvas selection metadata structure."""
    selection_position_range: CanvasSelectionMetadataSelectionPositionRange
    selection_type: str

    class Config:
        extra = "allow"


class Canvas(BaseModel):
    """Canvas structure."""
    create_source: str
    error_type: str
    from_version: int
    has_user_edit: bool
    is_failure: bool
    selection_metadata: CanvasSelectionMetadata
    textdoc_content_length: int
    textdoc_id: str
    textdoc_type: str
    title: str
    user_message_type: str
    version: int

    class Config:
        extra = "allow"


# ============================================================================
# CONTENT AND MEDIA STRUCTURES
# ============================================================================

class AudioAssetPointerMetadata(BaseModel):
    """Audio asset pointer metadata structure."""
    end: Optional[Union[float, int]] = None
    end_timestamp: Optional[Any] = None
    interruptions: Optional[Any] = None
    original_audio_source: Optional[Any] = None
    pretokenized_vq: Optional[Any] = None
    start: int
    start_timestamp: Optional[Any] = None
    transcription: Optional[Any] = None
    word_transcription: Optional[Any] = None

    class Config:
        extra = "allow"


class AudioAssetPointer(BaseModel):
    """Audio asset pointer structure."""
    asset_pointer: str
    content_type: str
    expiry_datetime: str
    format: str
    metadata: AudioAssetPointerMetadata
    size_bytes: int

    class Config:
        extra = "allow"


class ContentPartMetadataDalle(BaseModel):
    """Content part metadata dalle structure."""
    edit_op: Optional[Any] = None
    gen_id: Optional[Union[str, None]] = None
    parent_gen_id: Optional[Any] = None
    prompt: str
    seed: Optional[Union[int, None]] = None
    serialization_title: str

    class Config:
        extra = "allow"


class ContentPartMetadataGeneration(BaseModel):
    """Content part metadata generation structure."""
    gen_id: str
    gen_size: str
    height: int
    parent_gen_id: Optional[Any] = None
    seed: Optional[Any] = None
    serialization_title: str
    transparent_background: bool
    width: int

    class Config:
        extra = "allow"


class ContentPartMetadata(BaseModel):
    """Content part metadata structure."""
    asset_pointer_link: Optional[Any] = None
    container_pixel_height: Optional[Union[int, None]] = None
    container_pixel_width: Optional[Union[int, None]] = None
    dalle: Optional[ContentPartMetadataDalle] = None
    emu_omit_glimpse_image: Optional[Any] = None
    emu_patches_override: Optional[Any] = None
    generation: Optional[ContentPartMetadataGeneration] = None
    gizmo: Optional[Any] = None
    lpe_keep_patch_ijhw: Optional[Any] = None
    sanitized: bool
    watermarked_asset_pointer: Optional[Any] = None

    class Config:
        extra = "allow"


class ContentPartWorkspace(BaseModel):
    """Content part workspace structure."""
    app_id: str
    app_name: str
    content_type: str
    id: str
    title: str

    class Config:
        extra = "allow"


class ContentPart(BaseModel):
    """Content part structure."""
    asset_pointer: Optional[str] = None
    audio_asset_pointer: Optional[AudioAssetPointer] = None
    audio_start_timestamp: Optional[float] = None
    content_type: str
    context_parts: Optional[List[Dict[str, Any]]] = None
    custom_instructions: Optional[str] = None
    decoding_id: Optional[Any] = None
    direction: str
    expiry_datetime: str
    fovea: Optional[Union[int, None]] = None
    frames_asset_pointers: Optional[List[Any]] = None
    height: int
    metadata: Optional[ContentPartMetadata] = None
    size_bytes: int
    text: str
    video_container_asset_pointer: Optional[Any] = None
    width: int
    workspaces: Optional[List[ContentPartWorkspace]] = None

    class Config:
        extra = "allow"


class ContentThought(BaseModel):
    """Content thought structure."""
    content: str
    summary: str

    class Config:
        extra = "allow"


class ContentWorkspace(BaseModel):
    """Content workspace structure."""
    app_id: str
    app_name: str
    content_type: str
    id: str
    title: str

    class Config:
        extra = "allow"


class Attachment(BaseModel):
    """Attachment structure."""
    fileSizeTokens: Optional[int] = None
    fileTokenSize: int
    file_token_size: int
    height: int
    id: str
    mimeType: str
    mime_type: str
    name: str
    size: int
    url: str
    width: int

    class Config:
        extra = "allow"


class ImageResult(BaseModel):
    """Image result structure."""
    attribution: str
    content_size: Dict[str, int]
    content_url: str
    thumbnail_crop_info: Optional[Any] = None
    thumbnail_size: Dict[str, int]
    thumbnail_url: str
    title: str
    url: str

    class Config:
        extra = "allow"


# ============================================================================
# TASK AND ASYNC STRUCTURES
# ============================================================================

class AsyncTaskStatusMessages(BaseModel):
    """Async task status messages structure."""
    cancelled: str
    completed: str
    completed_no_time: str
    completed_with_time: str
    error: str
    initial: str

    class Config:
        extra = "allow"


class UserContextMessageData(BaseModel):
    """User context message data structure."""
    about_model_message: str
    about_user_message: str

    class Config:
        extra = "allow"


# ============================================================================
# OTHER METADATA STRUCTURES
# ============================================================================

class ModelSwitcherDeny(BaseModel):
    """Model switcher deny structure."""
    context: str
    description: str
    is_available: bool
    reason: str
    slug: str

    class Config:
        extra = "allow"


class ParagenVariantsInfo(BaseModel):
    """Paragen variants info structure."""
    conversation_id: str
    display_treatment: str
    num_variants_in_stream: int
    type: str

    class Config:
        extra = "allow"


class SerializationMetadataCustomSymbolOffset(BaseModel):
    """Serialization metadata custom symbol offset structure."""
    endIndex: int
    startIndex: int
    symbol: str

    class Config:
        extra = "allow"


class SerializationMetadata(BaseModel):
    """Serialization metadata structure."""
    custom_symbol_offsets: Optional[List[SerializationMetadataCustomSymbolOffset]] = None

    class Config:
        extra = "allow"


class SonicClassificationResult(BaseModel):
    """Sonic classification result structure."""
    classifier_config_name: str
    force_search_threshold: Optional[float] = None
    latency_ms: Optional[float] = None
    search_prob: Optional[Union[float, int]] = None

    class Config:
        extra = "allow"


class FinishDetails(BaseModel):
    """Finish details structure."""
    reason: str
    stop: str
    stop_tokens: Optional[List[Union[int, List[int]]]] = None
    type: str

    class Config:
        extra = "allow"


class Permission(BaseModel):
    """Permission structure."""
    notification_channel_id: str
    notification_channel_name: str
    notification_priority: int
    status: str
    type: str

    class Config:
        extra = "allow"


class AdaVisualization(BaseModel):
    """ADA visualization structure."""
    chart_type: str
    fallback_to_image: bool
    file_id: str
    title: str
    type: str

    class Config:
        extra = "allow"


class AppPairingTextFieldSelection(BaseModel):
    """App pairing text field selection structure."""
    end_line: int
    start_line: int

    class Config:
        extra = "allow"


class AppPairingTextField(BaseModel):
    """App pairing text field structure."""
    id: str
    name: str
    selection: AppPairingTextFieldSelection
    truncated_head_lines: int
    truncated_tail_lines: int

    class Config:
        extra = "allow"


class AppPairingSharedWorkspace(BaseModel):
    """App pairing shared workspace structure."""
    app_id: str
    app_name: str
    id: str
    text_fields: List[AppPairingTextField]
    title: str

    class Config:
        extra = "allow"


class AppPairing(BaseModel):
    """App pairing structure."""
    shared_workspaces: List[AppPairingSharedWorkspace]
    total_context_length: int
    type: str

    class Config:
        extra = "allow" 