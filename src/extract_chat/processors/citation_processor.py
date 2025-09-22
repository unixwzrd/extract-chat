from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..context.document_context import DocumentContext

MarkerKey = Tuple[int, int, int]
MARKER_PATTERN = re.compile(r"【(\d+)†L(\d+)-L(\d+)】")


@dataclass
class ReferenceEntry:
    """Normalized reference information gathered from markers and metadata."""

    key: MarkerKey
    seq: int
    title: str = ""
    url: str = ""
    text: str = ""
    pub_date: Optional[str] = None
    attribution: str = ""
    is_fallback: bool = False

    def merge(self, data: Dict[str, Any]) -> None:
        """Fill empty fields without overwriting existing values."""
        if not data:
            return

        if not self.title:
            title = _clean_str(data.get("title"))
            if title:
                self.title = title

        if not self.url:
            url = _clean_str(data.get("url"))
            if url:
                self.url = url

        if not self.text:
            text_value = _clean_str(data.get("text"))
            if text_value:
                self.text = text_value

        if self.pub_date in (None, ""):
            pub_date = data.get("pub_date")
            cleaned_date = _clean_str(pub_date)
            if cleaned_date:
                self.pub_date = cleaned_date

        if not self.attribution:
            attribution = _clean_str(data.get("attribution"))
            if attribution:
                self.attribution = attribution

    def to_payload(self, *, turn_prefix: int) -> Dict[str, Any]:
        ref_id, start_line, end_line = self.key
        return {
            "unique_id": f"{turn_prefix}_{self.seq}_{ref_id}_{start_line}_{end_line}",
            "turn_id": turn_prefix,
            "seq": self.seq,
            "ref_id": ref_id,
            "start_line": start_line,
            "end_line": end_line,
            "title": self.title,
            "url": self.url,
            "text": self.text,
            "pub_date": self.pub_date,
            "attribution": self.attribution,
            "is_fallback": self.is_fallback,
        }


class CitationProcessor:
    """Combine citations and content references into a single reference table."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._source_metadata_cache: Dict[str, Dict[int, str]] = {}

    def get_references_data(
        self,
        *,
        turn: Any,
        ref_turn_counter: int,
        start_seq: int = 1,
        existing_sequences: Optional[Dict[int, int]] = None,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], int]:
        refs_by_key, next_seq = self._seed_entries(turn)
        next_seq = self._merge_citations(turn, refs_by_key, next_seq)
        self._merge_content_references(turn, refs_by_key, next_seq)
        self._propagate_ref_metadata(refs_by_key)

        sources_metadata = self._extract_sources_metadata(turn)
        for entry in refs_by_key.values():
            if not entry.title or entry.title.startswith("Metadata missing"):
                fallback = sources_metadata.get(entry.key[0])
                if fallback:
                    entry.title = fallback
                    entry.text = entry.text or fallback
                    entry.is_fallback = True

        next_global_seq = self._assign_sequences(
            refs_by_key,
            start_seq=start_seq,
            existing_sequences=existing_sequences,
        )

        ordered_entries = sorted(
            refs_by_key.values(),
            key=lambda entry: (entry.seq, entry.key[0], entry.key[1], entry.key[2]),
        )
        payload = [entry.to_payload(turn_prefix=ref_turn_counter) for entry in ordered_entries]

        identity_seq_map: Dict[tuple, int] = {}
        for ref in payload:
            identity = _reference_identity_from_fields(
                ref.get("url"),
                ref.get("title"),
                ref.get("text"),
                ref.get("ref_id", 0),
                ref.get("seq", 0),
                bool(ref.get("is_fallback")),
            )
            if identity in identity_seq_map:
                ref["seq"] = identity_seq_map[identity]
            else:
                identity_seq_map[identity] = ref.get("seq", 0)
        return {"references": payload}, next_global_seq

    # ------------------------------------------------------------------
    # Marker extraction and initialization
    # ------------------------------------------------------------------
    def _seed_entries(self, turn: Any) -> Tuple[Dict[MarkerKey, ReferenceEntry], int]:
        seq_map = self._extract_marker_seq_map(turn)
        entries = {key: ReferenceEntry(key=key, seq=seq) for key, seq in seq_map.items()}
        next_seq = max(seq_map.values(), default=0) + 1
        return entries, next_seq

    def _extract_marker_seq_map(self, turn: Any) -> Dict[MarkerKey, int]:
        message = getattr(turn, "message", None)
        if message is None:
            return {}

        dc = DocumentContext.get()
        if dc:
            text = dc.extract_text_from_message(message)
            seq_map = dc.extract_marker_seq_map_from_text(text)
            if seq_map:
                return {(int(k[0]), int(k[1]), int(k[2])): v for k, v in seq_map.items()}

        text = self._fallback_text_from_message(message)
        seq_map: Dict[MarkerKey, int] = {}
        seq = 1
        for match in MARKER_PATTERN.finditer(text):
            key = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if key not in seq_map:
                seq_map[key] = seq
                seq += 1
        return seq_map

    def _fallback_text_from_message(self, message: Any) -> str:
        content = getattr(message, "content", None)
        if not content:
            return ""

        text_attr = getattr(content, "text", None)
        if isinstance(text_attr, str):
            return text_attr

        parts = getattr(content, "parts", None)
        if isinstance(parts, list):
            collected: List[str] = []
            for part in parts:
                if isinstance(part, str):
                    collected.append(part)
                    continue
                if hasattr(part, "text") and getattr(part, "text"):
                    collected.append(str(getattr(part, "text")))
                    continue
                if isinstance(part, dict):
                    value = part.get("text") or part.get("content")
                    if value:
                        collected.append(str(value))
                elif part:
                    collected.append(str(part))
            if collected:
                return "\n".join(collected)

        return ""

    # ------------------------------------------------------------------
    # Metadata merging
    # ------------------------------------------------------------------
    def _merge_citations(
        self,
        turn: Any,
        refs_by_key: Dict[MarkerKey, ReferenceEntry],
        next_seq: int,
    ) -> int:
        for entry in self._iter_citations(turn):
            key = self._key_from_citation(entry)
            target_key = self._resolve_key(key, refs_by_key)
            ref_entry, next_seq = self._ensure_entry(refs_by_key, target_key, next_seq)
            if ref_entry:
                ref_entry.merge(self._data_from_citation(entry))
        return next_seq

    def _merge_content_references(
        self,
        turn: Any,
        refs_by_key: Dict[MarkerKey, ReferenceEntry],
        next_seq: int,
    ) -> None:
        for entry in self._iter_content_references(turn):
            direct_key = self._parse_marker(entry.get("matched_text"))
            target_key = self._resolve_key(direct_key, refs_by_key)
            if target_key is None:
                target_key = self._find_key_by_title_url(entry, refs_by_key)
            ref_entry, next_seq = self._ensure_entry(refs_by_key, target_key or direct_key, next_seq)
            if ref_entry:
                ref_entry.merge(self._data_from_content_reference(entry))

    # ------------------------------------------------------------------
    # Citation helpers
    # ------------------------------------------------------------------
    def _iter_citations(self, turn: Any) -> Iterable[Dict[str, Any]]:
        message = getattr(turn, "message", None)
        metadata = getattr(message, "metadata", None)
        citations = []
        if hasattr(metadata, "citations") and getattr(metadata, "citations") is not None:
            citations = getattr(metadata, "citations")
        elif hasattr(metadata, "__getitem__"):
            citations = metadata.get("citations", [])

        for raw in citations or []:
            entry = _to_dict(raw)
            if not entry or entry.get("invalid_reason"):
                continue
            yield entry

    def _key_from_citation(self, entry: Dict[str, Any]) -> Optional[MarkerKey]:
        metadata = entry.get("metadata", {}) or {}
        extra = metadata.get("extra", {}) or {}
        try:
            cited_message_idx = extra.get("cited_message_idx")
            start_line_num = extra.get("start_line_num")
            end_line_num = extra.get("end_line_num")
            if cited_message_idx is None or start_line_num is None or end_line_num is None:
                return None
            return (int(cited_message_idx), int(start_line_num), int(end_line_num))
        except Exception:
            return None

    def _data_from_citation(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        metadata = entry.get("metadata", {}) or {}
        extra = metadata.get("extra", {}) or {}
        return {
            "title": metadata.get("title", ""),
            "url": metadata.get("url", ""),
            "text": metadata.get("text") or extra.get("evidence_text"),
            "pub_date": metadata.get("pub_date"),
            "attribution": metadata.get("source") or extra.get("connector_source"),
        }

    # ------------------------------------------------------------------
    # Content reference helpers
    # ------------------------------------------------------------------
    def _iter_content_references(self, turn: Any) -> Iterable[Dict[str, Any]]:
        message = getattr(turn, "message", None)
        metadata = getattr(message, "metadata", None)
        content_refs = []
        if hasattr(metadata, "content_references") and getattr(metadata, "content_references") is not None:
            content_refs = getattr(metadata, "content_references")
        elif hasattr(metadata, "__getitem__"):
            content_refs = metadata.get("content_references", [])

        for raw in content_refs or []:
            entry = _to_dict(raw)
            if not entry or entry.get("invalid"):
                continue
            yield entry

    def _data_from_content_reference(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        grouped = entry.get("grouped_webpages") or []
        for group in grouped:
            items = []
            if isinstance(group, dict):
                items = group.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                item_dict = _to_dict(item)
                if item_dict:
                    return {
                        "title": item_dict.get("title", ""),
                        "url": item_dict.get("url", ""),
                        "text": item_dict.get("snippet")
                        or item_dict.get("text")
                        or item_dict.get("description")
                        or item_dict.get("content"),
                        "pub_date": item_dict.get("pub_date"),
                        "attribution": item_dict.get("attribution", ""),
                    }
        return {
            "title": entry.get("title", ""),
            "url": entry.get("url", ""),
            "text": entry.get("snippet"),
            "pub_date": entry.get("pub_date"),
            "attribution": entry.get("attribution", ""),
        }

    # ------------------------------------------------------------------
    # Matching utilities
    # ------------------------------------------------------------------
    def _resolve_key(
        self,
        candidate: Optional[MarkerKey],
        refs_by_key: Dict[MarkerKey, ReferenceEntry],
    ) -> Optional[MarkerKey]:
        if candidate and candidate in refs_by_key:
            return candidate
        best = self._find_best_marker_key(candidate, refs_by_key)
        return best if best else candidate

    def _ensure_entry(
        self,
        refs_by_key: Dict[MarkerKey, ReferenceEntry],
        key: Optional[MarkerKey],
        next_seq: int,
    ) -> Tuple[Optional[ReferenceEntry], int]:
        if not key:
            return None, next_seq
        entry = refs_by_key.get(key)
        if entry:
            return entry, next_seq
        new_entry = ReferenceEntry(key=key, seq=next_seq)
        refs_by_key[key] = new_entry
        return new_entry, next_seq + 1

    def _parse_marker(self, text: Optional[str]) -> Optional[MarkerKey]:
        if not text:
            return None
        match = MARKER_PATTERN.search(text)
        if not match:
            return None
        try:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except Exception:
            return None

    def _find_best_marker_key(
        self,
        candidate: Optional[MarkerKey],
        refs_by_key: Dict[MarkerKey, ReferenceEntry],
    ) -> Optional[MarkerKey]:
        if not candidate:
            return None
        ref_id, start_line, end_line = candidate
        candidates = [key for key in refs_by_key if key[0] == ref_id]
        best_key: Optional[MarkerKey] = None
        best_score = -1
        for key in candidates:
            _, s2, e2 = key
            score = -999
            if s2 == start_line and abs(e2 - end_line) <= 2:
                score = 100 - abs(e2 - end_line)
            elif abs(s2 - start_line) <= 2:
                score = 50 + (e2 - s2)
            if score > best_score:
                best_score = score
                best_key = key
        return best_key if best_score >= 0 else None

    def _find_key_by_title_url(
        self,
        entry: Dict[str, Any],
        refs_by_key: Dict[MarkerKey, ReferenceEntry],
    ) -> Optional[MarkerKey]:
        url = _normalize_url(entry.get("url"))
        title = _normalize_text(entry.get("title"))

        grouped = entry.get("grouped_webpages")
        if isinstance(grouped, list):
            for group in grouped:
                group_dict = _to_dict(group)
                items = group_dict.get("items") if isinstance(group_dict, dict) else None
                if not isinstance(items, list):
                    continue
                for item in items:
                    item_dict = _to_dict(item)
                    if not item_dict:
                        continue
                    if not url:
                        url = _normalize_url(item_dict.get("url"))
                    if not title:
                        title = _normalize_text(item_dict.get("title"))
                    break
                if url or title:
                    break

        if not url and not title:
            return None

        best_key: Optional[MarkerKey] = None
        best_seq = 10**9
        for key, entry_obj in refs_by_key.items():
            info_url = _normalize_url(entry_obj.url)
            info_title = _normalize_text(entry_obj.title)
            match = False
            if url and info_url and (info_url == url or info_url in url or url in info_url):
                match = True
            elif title and info_title and (info_title in title or title in info_title):
                match = True
            if match and entry_obj.seq < best_seq:
                best_seq = entry_obj.seq
                best_key = key
        return best_key

    def _propagate_ref_metadata(self, refs_by_key: Dict[MarkerKey, ReferenceEntry]) -> None:
        """Ensure every reference entry has baseline bibliographic data across identical ref_ids."""
        fields = ["title", "url", "text", "attribution", "pub_date"]
        best_by_ref: Dict[int, Dict[str, Any]] = {}

        for entry in refs_by_key.values():
            ref_id = entry.key[0]
            store = best_by_ref.setdefault(ref_id, {field: "" for field in fields})
            for field in fields:
                value = getattr(entry, field)
                if isinstance(value, str):
                    value = value.strip()
                if value and not store[field]:
                    store[field] = value

        for entry in refs_by_key.values():
            ref_id = entry.key[0]
            donor = best_by_ref.get(ref_id, {})
            for field in fields:
                current = getattr(entry, field)
                if current:
                    continue
                fallback = donor.get(field)
                if fallback:
                    setattr(entry, field, fallback)

            if not entry.title:
                entry.title = f"Metadata missing for ref_id {ref_id}"

    def _extract_sources_metadata(self, turn: Any) -> Dict[int, str]:
        cache_key = getattr(turn, 'id', None)
        if cache_key and cache_key in self._source_metadata_cache:
            return self._source_metadata_cache[cache_key]

        message = getattr(turn, 'message', None)
        if message is None:
            return {}

        text = ""
        dc = DocumentContext.get()
        if dc:
            text = dc.extract_text_from_message(message)
        if not text:
            text = self._fallback_text_from_message(message)
        if not text:
            return {}

        lower_text = text.lower()
        idx = lower_text.find('sources:')
        if idx == -1:
            return {}
        sources_section = text[idx:]

        # Match numbered source entries
        pattern = re.compile(r'^\s*\d+\.\s*(.+?)(?=(?:\n\s*\d+\.|\Z))', re.MULTILINE | re.DOTALL)
        marker_pattern = re.compile(r'【(\d+)†L(\d+)-L(\d+)】')
        metadata: Dict[int, str] = {}

        for match in pattern.finditer(sources_section):
            entry_text = match.group(1).strip()
            if not entry_text:
                continue
            refs = marker_pattern.findall(entry_text)
            if not refs:
                continue
            # Remove markers from bibliographic text
            cleaned = marker_pattern.sub('', entry_text).strip()
            cleaned = cleaned.replace('*', '')
            cleaned = cleaned.rstrip('. ')
            # Normalize whitespace
            cleaned = re.sub(r'\s+', ' ', cleaned)
            if not cleaned:
                continue
            for ref_id_str, *_ in refs:
                try:
                    ref_id = int(ref_id_str)
                except (TypeError, ValueError):
                    continue
                metadata.setdefault(ref_id, cleaned)

        if cache_key:
            self._source_metadata_cache[cache_key] = metadata
        return metadata

    def _assign_sequences(
        self,
        refs_by_key: Dict[MarkerKey, ReferenceEntry],
        *,
        start_seq: int,
        existing_sequences: Optional[Dict[int, int]] = None,
    ) -> int:
        """Assign sequential citation numbers, ensuring duplicates reuse the same seq per ref_id."""

        identity_map: Dict[tuple, Dict[str, Any]] = {}
        for entry in refs_by_key.values():
            identity = self._reference_identity(entry)
            bucket = identity_map.setdefault(
                identity,
                {"entries": [], "first_seq": entry.seq},
            )
            bucket["entries"].append(entry)
            if entry.seq < bucket["first_seq"]:
                bucket["first_seq"] = entry.seq

        ordered = sorted(identity_map.items(), key=lambda item: (item[1]["first_seq"], item[0]))

        seq_counter = start_seq
        sequence_map = existing_sequences if existing_sequences is not None else {}

        for identity, data in ordered:
            if identity in sequence_map:
                assigned_seq = sequence_map[identity]
            else:
                assigned_seq = seq_counter
                sequence_map[identity] = assigned_seq
                seq_counter += 1
            for entry in data["entries"]:
                entry.seq = assigned_seq

        return seq_counter

    def _reference_identity(self, entry: ReferenceEntry) -> tuple:
        return _reference_identity_from_fields(
            entry.url,
            entry.title,
            entry.text,
            entry.key[0],
            entry.seq,
            entry.is_fallback,
        )


def _reference_identity_from_fields(
    url: Any,
    title: Any,
    text: Any,
    ref_id: int,
    seq: int,
    is_fallback: bool = False,
) -> tuple:
    url_norm = _normalize_url(url)
    fragment = ''
    base_url = url_norm
    if url_norm and '#:~:text=' in url_norm:
        base_url, fragment = url_norm.split('#:~:text=', 1)
    title_norm = _normalize_text(title)
    text_norm = _normalize_text(text)
    if not title_norm and not text_norm and is_fallback:
        title_norm = text_norm
    # Treat very short snippets/fragments as the same reference (e.g. one-word highlights)
    words = text_norm.split()
    if fragment and len(fragment) <= 120 and len(words) <= 3:
        fragment = ''
        text_norm = ''
    if base_url or title_norm or text_norm:
        return (base_url, fragment, title_norm or text_norm or '')
    return (ref_id, seq)


def _to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return value.dict()
        except Exception:
            pass
    return {}


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return ""


def _normalize_url(url: Any) -> str:
    value = _clean_str(url)
    if not value:
        return ""
    lower = value.lower().rstrip('/')
    return lower


def _normalize_text(text: Any) -> str:
    return _clean_str(text).lower()
