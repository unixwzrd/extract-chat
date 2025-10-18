from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from extract_chat.context.document_context import DocumentContext

MarkerKey = Tuple[int, int, int]
MARKER_PATTERN = re.compile(r"【(\d+)†L(\d+)-L(\d+)】")
SHORT_SNIPPET_WORD_LIMIT = 2


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
    source_label: str = ""
    skip_citation: bool = False
    reference_title: str = ""

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

        # Set reference_title: use source_label if available, otherwise use title
        if not self.reference_title:
            source_label = _clean_str(data.get("source_label"))
            if source_label:
                self.reference_title = source_label
            elif self.title:
                self.reference_title = self.title
        # Also update reference_title if source_label is provided and we don't have one yet
        if data.get("source_label") and not self.reference_title:
            self.reference_title = _clean_str(data.get("source_label"))

    def to_payload(self, *, turn_prefix: int, occurrence_index: int = 0) -> Dict[str, Any]:
        ref_id, start_line, end_line = self.key
        unique_suffix = f"_{occurrence_index}" if occurrence_index else "_0"
        return {
            "unique_id": f"{turn_prefix}_{self.seq}{unique_suffix}_{ref_id}_{start_line}_{end_line}",
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
            "source_label": self.source_label,
            "skip_citation": self.skip_citation,
            "reference_title": self.reference_title,
            "occurrence_index": occurrence_index,
        }


class CitationProcessor:
    """Combine citations and content references into a single reference table."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._source_metadata_cache: Dict[str, Dict[str, Dict[Any, str]]] = {}

    def get_references_data(
        self,
        *,
        turn: Any,
        ref_turn_counter: int,
        start_seq: int = 1,
        existing_sequences: Optional[Dict[int, int]] = None,
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], int]:
        refs_by_key, next_seq, marker_occurrences = self._seed_entries(turn)
        next_seq = self._merge_citations(turn, refs_by_key, next_seq)
        self._merge_content_references(turn, refs_by_key, next_seq)
        self._propagate_ref_metadata(refs_by_key)

        sources_by_key, sources_by_ref = self._extract_sources_metadata(turn)
        for entry in refs_by_key.values():
            fallback = sources_by_key.get(entry.key)
            if not fallback:
                fallback = sources_by_ref.get(entry.key[0])
            if fallback:
                entry.source_label = fallback
                if not entry.title or entry.title.startswith("Metadata missing"):
                    entry.title = fallback
                    if not entry.text:
                        entry.text = fallback
                    entry.is_fallback = True
                if entry.title and not entry.title.startswith("Metadata missing"):
                    entry.skip_citation = False
        # Set reference_title after source_label is populated
        for entry in refs_by_key.values():
            # Prefer canonical title, then source label, then snippet/url fallback
            if entry.title:
                entry.reference_title = entry.title
            elif entry.source_label:
                entry.reference_title = entry.source_label
            elif entry.text:
                entry.reference_title = entry.text
            elif entry.url:
                entry.reference_title = entry.url

        next_global_seq = self._assign_sequences(
            refs_by_key,
            start_seq=start_seq,
            existing_sequences=existing_sequences,
        )

        ordered_entries = sorted(
            refs_by_key.values(),
            key=lambda entry: (entry.seq, entry.key[0], entry.key[1], entry.key[2]),
        )

        occurrence_counts: Dict[MarkerKey, int] = {}
        payload: List[Dict[str, Any]] = []

        for key in marker_occurrences:
            entry = refs_by_key.get(key)
            if not entry:
                continue
            occ_index = occurrence_counts.get(key, 0)
            occurrence_counts[key] = occ_index + 1
            payload.append(entry.to_payload(turn_prefix=ref_turn_counter, occurrence_index=occ_index))

        # Include any references that were not present in the inline text (e.g. citation-only)
        for entry in ordered_entries:
            if occurrence_counts.get(entry.key, 0) == 0:
                payload.append(entry.to_payload(turn_prefix=ref_turn_counter, occurrence_index=0))
                occurrence_counts[entry.key] = 1

        for ref in payload:
            title_val = (ref.get("title") or "").strip()
            text_val = (ref.get("text") or "").strip()
            url_val = (ref.get("url") or "").strip()
            has_metadata = False
            if url_val:
                has_metadata = True
            elif title_val and not title_val.startswith("Metadata missing"):
                has_metadata = True
            elif text_val:
                has_metadata = True
            if not has_metadata:
                ref["skip_citation"] = True

        seq_occurrences: Dict[int, List[Dict[str, Any]]] = {}
        for ref in payload:
            seq_occurrences.setdefault(int(ref.get("seq", 0)), []).append(ref)

        for refs in seq_occurrences.values():
            if len(refs) == 1:
                refs[0]["occurrence_label"] = ""
                continue
            labels = _generate_occurrence_labels(len(refs))
            for label, ref in zip(labels, refs):
                ref["occurrence_label"] = label

        identity_seq_map: Dict[tuple, int] = {}
        for ref in payload:
            identity = _reference_identity_from_fields(
                ref.get("url"),
                ref.get("title"),
                ref.get("text"),
                ref.get("ref_id", 0),
                ref.get("seq", 0),
                bool(ref.get("is_fallback")),
                ref.get("source_label"),
                ref.get("attribution"),
                (ref.get("start_line"), ref.get("end_line")),
            )
            if identity in identity_seq_map:
                ref["seq"] = identity_seq_map[identity]
            else:
                identity_seq_map[identity] = ref.get("seq", 0)

        # Normalize sequence numbering so that the deduplicated reference list and
        # inline markers share the same contiguous numbering.
        try:
            from extract_chat.processors.reference_processing.reference_utils import (
                extract_reference_groups,
            )
        except ImportError:
            extract_reference_groups = None

        if extract_reference_groups:
            blocks = [
                {
                    "type": "assistant",
                    "references_table": {"references": payload},
                    "metadata": {"reference_turn_number": ref_turn_counter},
                }
            ]
            groups = extract_reference_groups(blocks)
            max_seq_assigned = 0
            for group in groups:
                meta = group.get("meta") or {}
                try:
                    seq_val = int(meta.get("seq", 0))
                except (TypeError, ValueError):
                    continue
                if seq_val > max_seq_assigned:
                    max_seq_assigned = seq_val
            if max_seq_assigned:
                next_global_seq = max(next_global_seq, max_seq_assigned + 1)

        return {"references": payload}, next_global_seq

    # ------------------------------------------------------------------
    # Marker extraction and initialization
    # ------------------------------------------------------------------
    def _seed_entries(self, turn: Any) -> Tuple[Dict[MarkerKey, ReferenceEntry], int, List[MarkerKey]]:
        seq_map, occurrences = self._extract_marker_seq_map(turn)
        entries = {key: ReferenceEntry(key=key, seq=seq) for key, seq in seq_map.items()}
        next_seq = max(seq_map.values(), default=0) + 1
        return entries, next_seq, occurrences

    def _extract_marker_seq_map(self, turn: Any) -> Tuple[Dict[MarkerKey, int], List[MarkerKey]]:
        message = getattr(turn, "message", None)
        if message is None:
            return {}, []

        text = ""
        dc = DocumentContext.get()
        if dc:
            text = dc.extract_text_from_message(message)
        if not text:
            text = self._fallback_text_from_message(message)
        return self._parse_markers_from_text(text)

    def _parse_markers_from_text(self, text: str) -> Tuple[Dict[MarkerKey, int], List[MarkerKey]]:
        seq_map: Dict[MarkerKey, int] = {}
        occurrences: List[MarkerKey] = []
        seq = 1
        if not text:
            return seq_map, occurrences
        for match in MARKER_PATTERN.finditer(text):
            key = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            occurrences.append(key)
            if key not in seq_map:
                seq_map[key] = seq
                seq += 1
        return seq_map, occurrences

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

            data = self._data_from_content_reference(entry)

            chosen_key = target_key or direct_key
            existing_entry = refs_by_key.get(chosen_key) if chosen_key else None

            if (
                existing_entry
                and direct_key
                and direct_key != chosen_key
            ):
                existing_identity = self._reference_identity(existing_entry)
                prospective_identity = _reference_identity_from_fields(
                    data.get("url"),
                    data.get("title"),
                    data.get("text"),
                    existing_entry.key[0],
                    existing_entry.seq,
                    existing_entry.is_fallback,
                    data.get("source_label"),
                    data.get("attribution"),
                    direct_key[1:],
                )
                if prospective_identity != existing_identity:
                    chosen_key = direct_key
                    existing_entry = None

            if chosen_key is None:
                chosen_key = self._allocate_virtual_key(refs_by_key)

            ref_entry, next_seq = self._ensure_entry(refs_by_key, chosen_key, next_seq)
            if ref_entry:
                ref_entry.merge(data)

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
            "source_label": metadata.get("source_label", ""),
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
                        "source_label": item_dict.get("source_label", ""),
                    }
        return {
            "title": entry.get("title", ""),
            "url": entry.get("url", ""),
            "text": entry.get("snippet"),
            "pub_date": entry.get("pub_date"),
            "attribution": entry.get("attribution", ""),
            "source_label": entry.get("source_label", ""),
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
        fields = ["title", "url", "text", "attribution", "pub_date", "source_label"]
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
                entry.skip_citation = True
            elif entry.title.startswith("Metadata missing"):
                entry.skip_citation = True
            elif not any([entry.url, entry.text, entry.source_label]):
                # No usable bibliographic data, suppress citation
                entry.skip_citation = True

    def _extract_sources_metadata(self, turn: Any) -> Tuple[Dict[MarkerKey, str], Dict[int, str]]:
        cache_key = getattr(turn, 'id', None)
        if cache_key and cache_key in self._source_metadata_cache:
            cached = self._source_metadata_cache[cache_key]
            return cached["per_key"], cached["per_ref"]

        message = getattr(turn, 'message', None)
        if message is None:
            empty = ({}, {})
            return empty

        text = ""
        dc = DocumentContext.get()
        if dc:
            text = dc.extract_text_from_message(message)
        if not text:
            text = self._fallback_text_from_message(message)
        if not text:
            empty = ({}, {})
            return empty

        lower_text = text.lower()
        idx = lower_text.find('sources:')
        if idx == -1:
            empty = ({}, {})
            return empty
        sources_section = text[idx:]

        # Match numbered source entries
        pattern = re.compile(r'^\s*\d+\.\s*(.+?)(?=(?:\n\s*\d+\.|\Z))', re.MULTILINE | re.DOTALL)
        marker_pattern = re.compile(r'【(\d+)†L(\d+)-L(\d+)】')
        per_key: Dict[MarkerKey, str] = {}
        per_ref: Dict[int, str] = {}

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
            for ref_id_str, start_line_str, end_line_str in refs:
                try:
                    ref_id = int(ref_id_str)
                    start_line = int(start_line_str)
                    end_line = int(end_line_str)
                except (TypeError, ValueError):
                    continue
                key = (ref_id, start_line, end_line)
                per_key.setdefault(key, cleaned)
                per_ref.setdefault(ref_id, cleaned)

        if cache_key:
            self._source_metadata_cache[cache_key] = {"per_key": per_key, "per_ref": per_ref}
        return per_key, per_ref

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
            entry.source_label,
            entry.attribution,
            entry.key[1:],
        )

    def _allocate_virtual_key(self, refs_by_key: Dict[MarkerKey, ReferenceEntry]) -> MarkerKey:
        """Generate a synthetic marker key when no direct one is available."""

        if refs_by_key:
            ref_id = max(key[0] for key in refs_by_key.keys()) + 1
        else:
            ref_id = 1
        base = 1_000_000
        offset = 0
        while True:
            candidate = (ref_id, base + offset, base + offset + 1)
            if candidate not in refs_by_key:
                return candidate
            offset += 2


def _reference_identity_from_fields(
    url: Any,
    title: Any,
    text: Any,
    ref_id: int,
    seq: int,
    is_fallback: bool = False,
    source_label: Any = "",
    attribution: Any = "",
    line_range: tuple[Any, Any] | None = None,
) -> tuple:
    url_norm = _normalize_url(url)
    fragment = ""
    base_url = url_norm
    if url_norm and "#" in url_norm:
        base_url, fragment = url_norm.split('#', 1)
    canonical_title = source_label if source_label else title
    title_norm = _normalize_text(canonical_title)
    text_norm = _normalize_text(text)
    if not title_norm and not text_norm and is_fallback:
        title_norm = text_norm
    label_norm = _normalize_text(source_label)
    attr_norm = _normalize_text(attribution)
    raw_text = text or ""
    text_word_count = len(re.findall(r"\b\w+\b", raw_text))

    identity_text = title_norm or text_norm or ''
    if title_norm and text_norm and text_word_count > SHORT_SNIPPET_WORD_LIMIT:
        identity_text = f"{title_norm}@@snippet::{text_norm}"
    if label_norm:
        if not identity_text:
            identity_text = label_norm
        elif not base_url:
            label_redundant = label_norm == identity_text or (
                attr_norm and label_norm == attr_norm
            )
            if not label_redundant:
                identity_text = f"{identity_text}::{label_norm}" if identity_text else label_norm
    elif attr_norm and not identity_text:
        identity_text = attr_norm
    extras: list[str] = []
    if not identity_text and fragment:
        extras.append(fragment)
    if (
        base_url
        and not identity_text
        and line_range
        and all(x is not None for x in line_range)
    ):
        start_line, end_line = line_range
        extras.append(f"{start_line}-{end_line}")
    if extras:
        extra_tag = "::".join(extras)
        identity_text = f"{identity_text}@@{extra_tag}" if identity_text else extra_tag
    if base_url or identity_text:
        return (base_url, identity_text)
    return (ref_id, seq)


def _generate_occurrence_labels(count: int) -> List[str]:
    """Generate stable alphabetic labels (a, b, ...)."""
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    labels: List[str] = []
    for idx in range(count):
        label = ""
        n = idx
        while True:
            label = alphabet[n % 26] + label
            n = n // 26 - 1
            if n < 0:
                break
        labels.append(label)
    return labels


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
