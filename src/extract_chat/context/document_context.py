"""
DocumentContext - a lightweight, testable singleton for sharing the loaded
conversation object (and convenient indexes) across processor modules.

Design goals:
- Use contextvars so concurrent runs (threads/async tasks) don't collide
- Keep explicit initialization at the app entrypoint
- Preserve testability: modules may still accept explicit objects; context is optional
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional, Tuple


class DocumentContext:
    """Holds the current conversation and fast-access indexes.

    Initialize once at program start with initialize(conversation=...).
    Retrieve anywhere via DocumentContext.get().
    """

    _current_context: ContextVar[Optional["DocumentContext"]] = ContextVar(
        "document_context",
        default=None,
    )

    def __init__(self, *, conversation: Any, verbose: bool = False):
        self.conversation: Any = conversation
        self.turn_index: Dict[str, Any] = {}
        self._cite_pattern = re.compile(r'【(\d+)†L(\d+)-L(\d+)】')
        self.verbose: bool = bool(verbose)

        mapping = getattr(conversation, "mapping", None)
        if isinstance(mapping, dict):
            # Directly reuse mapping if it is already id->turn_data
            self.turn_index = mapping

    # ---- Lifecycle ----
    @classmethod
    def initialize(cls, *, conversation: Any, verbose: bool = False) -> "DocumentContext":
        """Create and set the current context for this execution scope."""
        ctx = cls(conversation=conversation, verbose=verbose)
        cls._current_context.set(ctx)
        return ctx

    @classmethod
    def get(cls) -> Optional["DocumentContext"]:
        """Get the current context or None if unset."""
        try:
            return cls._current_context.get()
        except LookupError:
            return None

    @classmethod
    def reset(cls) -> None:
        """Clear the current context (useful in tests)."""
        cls._current_context.set(None)

    # ---- Debug helpers ----
    def is_verbose(self) -> bool:
        try:
            return bool(self.verbose)
        except Exception:
            return False

    # ---- Helpers ----
    def get_turn(self, turn_id: str) -> Optional[Any]:
        """Return the turn object by id if available."""
        if not self.turn_index:
            return None
        return self.turn_index.get(turn_id)

    def get_mapping(self) -> Dict[str, Any]:
        """Return the raw mapping id->turn_data (read-only usage expected)."""
        return self.turn_index or {}

    # ---- Conversation structure helpers ----
    def get_root_turn_ids(self) -> List[str]:
        """Return ids of root turns.

        Prefer turns whose parent is None, but if none found, treat any turn
        whose parent is missing from mapping as a root (common in exports).
        """
        roots: List[str] = []
        mapping = self.turn_index or {}
        # First pass: strict None parents
        for turn_id, turn_data in mapping.items():
            parent = None
            try:
                if hasattr(turn_data, '__getitem__'):
                    parent = turn_data.get('parent', None)
                else:
                    parent = getattr(turn_data, 'parent', None)
            except Exception:
                parent = None
            if parent is None:
                roots.append(turn_id)
        if roots:
            return roots
        # Fallback: parent not in mapping
        for turn_id, turn_data in mapping.items():
            try:
                if hasattr(turn_data, '__getitem__'):
                    parent = turn_data.get('parent', None)
                else:
                    parent = getattr(turn_data, 'parent', None)
            except Exception:
                parent = None
            if parent is None or (parent not in mapping):
                roots.append(turn_id)
        return roots

    def get_children_ids(self, turn_id: str) -> List[str]:
        """Return ordered child ids for a given turn id."""
        turn = self.get_turn(turn_id)
        if not turn:
            return []
        try:
            if hasattr(turn, '__getitem__'):
                children = turn.get('children', [])
            else:
                children = getattr(turn, 'children', [])
        except Exception:
            children = []
        return list(children) if isinstance(children, list) else []

    def _preorder_collect(self, turn_id: str, *, level: int, out: List[Tuple[str, int]], visited: set) -> None:
        if turn_id in visited:
            return
        visited.add(turn_id)
        out.append((turn_id, level))
        for child_id in self.get_children_ids(turn_id):
            self._preorder_collect(child_id, level=level + 1, out=out, visited=visited)

    def get_preorder_turn_ids_with_levels(self) -> List[Tuple[str, int]]:
        """Return a stable pre-order traversal of the conversation tree with nesting level."""
        order: List[Tuple[str, int]] = []
        visited: set = set()
        for root_id in self.get_root_turn_ids():
            self._preorder_collect(root_id, level=0, out=order, visited=visited)
        return order

    def iter_preorder(self) -> Iterator[Tuple[str, Any, int]]:
        """Yield (turn_id, turn_data, level) in pre-order."""
        for turn_id, level in self.get_preorder_turn_ids_with_levels():
            turn = self.get_turn(turn_id)
            if turn is not None:
                yield turn_id, turn, level

    @staticmethod
    def _turn_timestamp(turn: Any) -> Optional[float]:
        """Return the message timestamp, falling back to the containing node."""

        try:
            message = turn.get("message") if isinstance(turn, dict) else getattr(turn, "message", None)
            value = message.get("create_time") if isinstance(message, dict) else getattr(message, "create_time", None)
            if value is None:
                value = turn.get("create_time") if isinstance(turn, dict) else getattr(turn, "create_time", None)
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def iter_chronological(self) -> Iterator[Tuple[str, Any, int]]:
        """Yield every exported node in stable message-timestamp order."""

        indexed_turns = list(enumerate((self.turn_index or {}).items()))
        indexed_turns.sort(
            key=lambda item: (
                self._turn_timestamp(item[1][1]) is None,
                self._turn_timestamp(item[1][1]) or 0.0,
                item[0],
            )
        )
        for _index, (turn_id, turn) in indexed_turns:
            yield turn_id, turn, 0

    # ---- Message/content helpers ----
    def extract_text_from_content(self, content: Any) -> str:
        """Extract human-readable text from a message content object or raw text.

        This consolidates logic used across processors.
        """
        if not content:
            return ""

        # Direct text attribute
        text = getattr(content, 'text', None)
        if text:
            try:
                return str(text)
            except Exception:
                pass

        # parts: list of strings, dicts, or objects with .text
        parts = getattr(content, 'parts', None)
        if isinstance(parts, list):
            text_parts: List[str] = []
            for part in parts:
                if part is None:
                    continue
                try:
                    if hasattr(part, 'text') and getattr(part, 'text'):
                        text_parts.append(str(getattr(part, 'text')))
                    elif isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict):
                        if part.get('text'):
                            text_parts.append(str(part.get('text')))
                    else:
                        s = str(part)
                        if '【' in s and '†' in s and 'L' in s:
                            text_parts.append(s)
                except Exception:
                    continue
            if text_parts:
                return "\n".join(text_parts)

        # Common alternate fields
        for field in ['thoughts', 'model_set_context', 'repository', 'repo_summary', 'user_profile', 'user_instructions']:
            value = getattr(content, field, None)
            if value:
                try:
                    return str(value)
                except Exception:
                    pass

        # Already a string
        if isinstance(content, str):
            return content

        return ""

    def extract_text_from_message(self, message: Any) -> str:
        """Extract text from a message object that has a .content field or is a mapping."""
        if not message:
            return ""
        try:
            if hasattr(message, 'content') and message.content is not None:
                return self.extract_text_from_content(message.content)
            if isinstance(message, dict) and message.get('content'):
                return self.extract_text_from_content(message.get('content'))
        except Exception:
            pass
        return ""

    def has_references_in_text(self, text: str) -> bool:
        if not text:
            return False
        try:
            return bool(self._cite_pattern.search(text))
        except Exception:
            return False

    def has_references_in_message(self, message: Any) -> bool:
        """Check for citations or content references via metadata or inline markers."""
        if not message:
            return False
        # Metadata detection
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
        # Inline markers
        text = self.extract_text_from_message(message)
        return self.has_references_in_text(text)

    # ---- Metadata helpers ----
    def get_metadata(self, message: Any) -> Dict[str, Any]:
        meta = getattr(message, 'metadata', None)
        if not meta:
            return {}
        if hasattr(meta, 'items'):
            try:
                return dict(meta)
            except Exception:
                pass
        # Fallback: attempt attribute-style access with known fields
        result: Dict[str, Any] = {}
        for key in ['citations', 'content_references', 'request_id', 'model_slug', 'end_turn', 'user_context_message_data']:
            try:
                result[key] = getattr(meta, key)
            except Exception:
                pass
        return result

    def get_citations(self, message: Any) -> List[Dict[str, Any]]:
        meta = getattr(message, 'metadata', None)
        if hasattr(meta, 'citations') and getattr(meta, 'citations') is not None:
            return getattr(meta, 'citations')
        if hasattr(meta, '__getitem__'):
            return meta.get('citations', [])
        return []

    # ---- Citation markers helpers ----
    def extract_marker_keys_from_text(self, text: str) -> List[tuple]:
        """Return a list of (ref_id, start_line, end_line) keys in order of appearance."""
        if not text:
            return []
        keys: List[tuple] = []
        try:
            for m in self._cite_pattern.finditer(text):
                try:
                    ref_id = int(m.group(1))
                    s = int(m.group(2))
                    e = int(m.group(3))
                    k = (ref_id, s, e)
                    if k not in keys:
                        keys.append(k)
                except Exception:
                    continue
        except Exception:
            return []
        return keys

    def extract_marker_seq_map_from_text(self, text: str) -> Dict[tuple, int]:
        """Return a dict mapping (ref_id,start,end) -> sequence number by first appearance."""
        seq_map: Dict[tuple, int] = {}
        if not text:
            return seq_map
        seq = 1
        for key in self.extract_marker_keys_from_text(text):
            if key not in seq_map:
                seq_map[key] = seq
                seq += 1
        return seq_map

    # ---- Conversation-context convenience ----
    def get_user_context_data(self, message: Any) -> Dict[str, Any]:
        """Return the user_context_message_data block regardless of storage location."""
        result: Dict[str, Any] = {}
        if not message:
            return result
        meta = getattr(message, 'metadata', None)
        if meta and hasattr(meta, 'get'):
            try:
                result = meta.get('user_context_message_data', {}) or {}
            except Exception:
                result = {}
        # Some schemas store it directly on the message
        try:
            direct = getattr(message, 'user_context_message_data', None)
            if isinstance(direct, dict) and direct:
                result = direct
        except Exception:
            pass
        return result or {}

    def get_content_references(self, message: Any) -> List[Dict[str, Any]]:
        meta = getattr(message, 'metadata', None)
        if hasattr(meta, 'content_references') and getattr(meta, 'content_references') is not None:
            return getattr(meta, 'content_references')
        if hasattr(meta, '__getitem__'):
            return meta.get('content_references', [])
        return []

    # ---- Conversation-level getters ----
    def get_title(self) -> Optional[str]:
        return getattr(self.conversation, 'title', None)

    def get_conversation_id(self) -> Optional[str]:
        return getattr(self.conversation, 'conversation_id', None)

    def get_create_time(self) -> Optional[float]:
        return getattr(self.conversation, 'create_time', None)

    def get_update_time(self) -> Optional[float]:
        return getattr(self.conversation, 'update_time', None)

    def get_default_model_slug(self) -> Optional[str]:
        return getattr(self.conversation, 'default_model_slug', None)

    # ---- Turn/message convenience ----
    def get_message(self, turn_id: str) -> Optional[Any]:
        turn = self.get_turn(turn_id)
        return getattr(turn, 'message', None) if turn else None

    def get_message_text(self, turn_id: str) -> str:
        msg = self.get_message(turn_id)
        return self.extract_text_from_message(msg) if msg is not None else ""

    # ---- Cursor/Navigator ----
    class TurnCursor:
        """A simple cursor to walk turns in pre-order while holding levels."""

        def __init__(self, context: 'DocumentContext'):
            self._context = context
            self._order: List[Tuple[str, int]] = context.get_preorder_turn_ids_with_levels()
            self._index: int = 0

        def reset(self) -> None:
            self._index = 0

        def has_next(self) -> bool:
            return self._index < len(self._order)

        def current(self) -> Optional[Tuple[str, Any, int]]:
            if not self._order or self._index >= len(self._order):
                return None
            turn_id, level = self._order[self._index]
            return turn_id, self._context.get_turn(turn_id), level

        def next(self) -> Optional[Tuple[str, Any, int]]:
            cur = self.current()
            if cur is None:
                return None
            self._index += 1
            return cur

        def peek(self) -> Optional[Tuple[str, Any, int]]:
            if not self._order or self._index + 1 >= len(self._order):
                return None
            turn_id, level = self._order[self._index + 1]
            return turn_id, self._context.get_turn(turn_id), level
