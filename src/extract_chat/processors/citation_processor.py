import re
from typing import Any, Dict, Optional, Tuple

from ..context.document_context import DocumentContext


class CitationProcessor:
    """Process citations and references from conversation data."""

    def __init__(self):
        pass

    def _get_text_content_from_message(self, message) -> str:
        """Extract text content from a message."""
        dc = DocumentContext.get()
        if dc:
            return dc.extract_text_from_message(message)
        # Fallback local behavior if context is absent
        try:
            if hasattr(message, 'content') and message.content:
                if isinstance(message.content, str):
                    return message.content
                return str(message.content)
            if isinstance(message, dict) and message.get('content'):
                return str(message.get('content'))
        except Exception:
            pass
        return ""

    def _parse_marker(self, text: Optional[str]) -> Optional[Tuple[int, int, int]]:
        """Parse a single marker like '【X†LY-LZ】' and return (ref_id, start_line, end_line)."""
        if not text:
            return None
        try:
            m = re.search(r'【(\d+)†L(\d+)-L(\d+)】', text)
            if m:
                return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None
        return None

    def get_references_data(self, *, turn, ref_turn_counter: int) -> Dict:
        """
        Get references data from a specific turn and return reference block.

        Args:
            turn_id: The turn ID to get references from
            ref_turn_counter: The counter for turns with references (1st, 2nd, 3rd, etc.)

        Returns:
            Dictionary containing reference data for this turn
                {
                    'references': [
                        {
                            'unique_id': str,      # Format: "{ref_turn_counter}_{ref_id}_{start_line}_{end_line}"
                            'seq': int,            # Sequence number in text order
                            'ref_id': int,         # Reference ID from marker (first number in 【X†LY-LZ】)
                            'start_line': int,     # Start line from marker
                            'end_line': int,       # End line from marker
                            'title': str,          # Title of the reference
                            'url': str,            # URL of the reference
                            'text': str,           # Quoted text or snippet
                            'pub_date': str,       # Publication date
                            'attribution': str     # Source attribution
                        }
                    ]
                }
        """
        # Step 1: Extract citation markers from this turn (source of truth for ordering)
        citation_markers = self._extract_citation_markers_from_turn(turn)

        # No fallback seeding: text markers are source of truth

        # Initialize flat refs-by-key table from markers (fill defaults)
        refs_by_key = self._init_refs_from_keys(citation_markers)

        # Print TEXT keys in a standard format for external reconciliation
        try:
            for key, _ in sorted(citation_markers.items(), key=lambda kv: kv[1]):
                ref_id, s, e = key
                print(f"{int(ref_id)},{int(s)},{int(e)}")
        except Exception:
            pass

        # Populate from metadata.citations (fill-only-empty; skip invalid)
        self._merge_citations_into_refs(turn=turn, refs_by_key=refs_by_key)

        # Populate from metadata.content_references (fill-only-empty; skip invalid)
        self._merge_content_refs_into_refs(turn=turn, refs_by_key=refs_by_key)

        # Unconditional debug dump: print every entry with a title from both lists (numbers only)
        self._print_all_titles_with_triplets(turn)

        # Emit flat list in seq order with stable unique ids (turn-scoped)
        references_list = self._emit_references_list(refs_by_key=refs_by_key, ref_turn_counter=ref_turn_counter)

        return {"references": references_list}

    def extract_key(self, entry, *, is_citation: bool) -> Optional[Tuple]:
        """Extract key from citation or content_reference entry."""
        try:
            if is_citation:
                # Correct location: entry['metadata']['extra']
                meta = entry.get('metadata', {}) if isinstance(entry, dict) else {}
                extra = meta.get('extra', {}) if isinstance(meta, dict) else {}
                cited_message_idx = extra.get('cited_message_idx')
                start_line_num = extra.get('start_line_num')
                end_line_num = extra.get('end_line_num')
                if cited_message_idx is not None and start_line_num is not None and end_line_num is not None:
                    return (int(cited_message_idx), int(start_line_num), int(end_line_num))
            else:
                base = entry if isinstance(entry, dict) else {}
                matched_text = base.get('matched_text', '')
                return self._parse_marker(matched_text)
        except Exception:
            return None
        return None

    def extract_data(self, entry: Dict[str, Any], *, is_citation: bool) -> Dict[str, Any]:
        """Extract normalized fields from a citation or content_reference entry.
        Returns a dict with keys: title, url, text, pub_date, attribution.
        """
        if not isinstance(entry, dict):
            entry = entry.dict() if hasattr(entry, 'dict') else {}
        if not entry:
            return {'title': '', 'url': '', 'text': '', 'pub_date': None, 'attribution': ''}

        if is_citation:
            meta = entry.get('metadata', {}) or {}
            extra = meta.get('extra', {}) or {}
            title = meta.get('title', '')
            url = meta.get('url', '')
            text = meta.get('text') or (extra.get('evidence_text') if isinstance(extra, dict) else '') or ''
            pub_date = meta.get('pub_date')
            attribution = (meta.get('source') or (extra.get('connector_source') if isinstance(extra, dict) else '') or '')
            return {
                'title': title or '',
                'url': url or '',
                'text': text or '',
                'pub_date': pub_date,
                'attribution': attribution or '',
            }
        # content_reference
        grouped_webpages = entry.get('grouped_webpages', []) or []
        # Prefer first item from grouped_webpages if available
        for group in grouped_webpages:
            for item in (group.get('items', []) or []):
                return {
                    'title': item.get('title', '') or '',
                    'url': item.get('url', '') or '',
                    'text': item.get('snippet', '') or '',
                    'pub_date': item.get('pub_date'),
                    'attribution': item.get('attribution', '') or '',
                }
        # Fallback to top-level fields
        return {
            'title': entry.get('title', '') or '',
            'url': entry.get('url', '') or '',
            'text': entry.get('snippet', '') or '',
            'pub_date': entry.get('pub_date'),
            'attribution': entry.get('attribution', '') or '',
        }

    def fill_if_empty(self, target: Dict, source: Dict):
        """Fill target dict with source data only if target fields are empty."""
        for field in ['title', 'url', 'text', 'pub_date', 'attribution']:
            if not target[field] and source.get(field):
                target[field] = source[field].strip() if isinstance(source[field], str) else source[field]
                if field == 'title':
                    print(f"DEBUG: Added {field}: '{source[field][:50]}...' to target")
                    print(f"DEBUG: Target title is now: '{target[field][:50]}...'")

    def _extract_citation_markers_from_turn(self, turn) -> Dict[Tuple[int, int, int], int]:
        """
        Extract citation markers from a specific turn and assign sequence numbers.

        Args:
            turn: The turn object containing the message

        Returns:
            Dictionary with triplet (ref_id, start_line, end_line) as key and sequence number as value
        """
        if not turn or not turn.message:
            return {}

        # Get message text from turn
        message = turn.message
        text_content = self._get_text_content_from_message(message)
        if not text_content:
            return {}

        # Extract citation markers using DocumentContext helper when available
        dc = DocumentContext.get()
        if dc:
            return dc.extract_marker_seq_map_from_text(text_content)

        # Fallback: regex in this module
        pattern = r'【(\d+)†L(\d+)-L(\d+)】'
        citation_markers = {}
        seq_num = 1
        for match in re.finditer(pattern, text_content):
            key = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if key not in citation_markers:
                citation_markers[key] = seq_num
                seq_num += 1
        return citation_markers

    def _print_all_titles_with_triplets(self, turn) -> None:
        """Print numeric triplets and titles for every entry that has a title in both arrays, regardless of validity or match."""
        try:
            meta = getattr(turn.message, 'metadata', None)
            if not meta:
                return
            # Citations
            citations = []
            if hasattr(meta, 'citations') and getattr(meta, 'citations') is not None:
                citations = getattr(meta, 'citations')
            elif hasattr(meta, '__getitem__'):
                citations = meta.get('citations', [])
            for raw in citations or []:
                entry = raw if isinstance(raw, dict) else (raw.dict() if hasattr(raw, 'dict') else {})
                if not entry:
                    continue
                m = entry.get('metadata', {}) or {}
                title = (m.get('title') or '').strip()
                extra = m.get('extra') or {}
                cm = extra.get('cited_message_idx')
                s = extra.get('start_line_num')
                e = extra.get('end_line_num')
                if title and cm is not None and s is not None and e is not None:
                    safe_title = title.replace('"', '""')
                    print(f'{int(cm)},{int(s)},{int(e)},"{safe_title}"')
            # Content references
            content_refs = []
            if hasattr(meta, 'content_references') and getattr(meta, 'content_references') is not None:
                content_refs = getattr(meta, 'content_references')
            elif hasattr(meta, '__getitem__'):
                content_refs = meta.get('content_references', [])
            for raw in content_refs or []:
                entry = raw if isinstance(raw, dict) else (raw.dict() if hasattr(raw, 'dict') else {})
                if not entry:
                    continue
                title = ''
                gw = entry.get('grouped_webpages') or []
                if isinstance(gw, list) and gw and isinstance(gw[0], dict):
                    items = gw[0].get('items') or []
                    if isinstance(items, list) and items and isinstance(items[0], dict):
                        title = (items[0].get('title') or '').strip()
                if not title:
                    title = (entry.get('title') or '').strip()
                key = self._parse_marker(entry.get('matched_text', ''))
                if title and key:
                    rid, s2, e2 = key
                    safe_title = title.replace('"', '""')
                    print(f'{int(rid)},{int(s2)},{int(e2)},"{safe_title}"')
        except Exception:
            return

    # (fallback seeding removed)

    def _init_refs_from_keys(self, citation_markers: Dict[Tuple[int, int, int], int]) -> Dict[Tuple[int, int, int], Dict[str, Any]]:
        refs_by_key: Dict[Tuple[int, int, int], Dict[str, Any]] = {}
        for key, seq in citation_markers.items():
            ref_id, start_line, end_line = key
            refs_by_key[key] = {
                'seq': seq,
                'ref_id': ref_id,
                'start_line': start_line,
                'end_line': end_line,
                'title': '',
                'url': '',
                'text': '',
                'pub_date': None,
                'attribution': '',
                'lines': {(start_line, end_line)},
            }
        return refs_by_key

    def _emit_references_list(self, *, refs_by_key: Dict[Tuple[int, int, int], Dict[str, Any]], ref_turn_counter: int) -> list:
        references_list = []
        for key in sorted(refs_by_key.keys(), key=lambda k: refs_by_key[k]['seq']):
            info = refs_by_key[key]
            ref_id, start_line, end_line = key
            references_list.append({
                'unique_id': f"{ref_turn_counter}_{ref_id}_{start_line}_{end_line}",
                'seq': info['seq'],
                'ref_id': ref_id,
                'start_line': start_line,
                'end_line': end_line,
                'title': info.get('title', ''),
                'url': info.get('url', ''),
                'text': info.get('text', ''),
                'pub_date': info.get('pub_date'),
                'attribution': info.get('attribution', ''),
            })
        return references_list

    # Debug printer removed to keep module minimal

    # Summary helper removed to keep module minimal

    def _find_best_marker_key(
        self,
        *,
        entry_key: Optional[Tuple[int, int, int]],
        refs_by_key: Dict[Tuple[int, int, int], Dict[str, Any]]
    ) -> Optional[Tuple[int, int, int]]:
        """Find the closest existing marker key when exact key is absent.
        Tolerance policy:
          - same ref_id required
          - prefer same start, abs(end - end_candidate) <= 2
          - else allow abs(start - start_candidate) <= 2 and pick the longer span
        """
        if not entry_key:
            return None
        ref_id, start_line, end_line = entry_key
        candidates = [k for k in refs_by_key.keys() if k[0] == ref_id]
        if not candidates:
            return None
        best = None
        best_score = -1
        for cand in candidates:
            _, s2, e2 = cand
            score = -9999
            if s2 == start_line and abs(e2 - end_line) <= 2:
                score = 100 - abs(e2 - end_line)
            elif abs(s2 - start_line) <= 2:
                span = e2 - s2
                score = 50 + span
            if score > best_score:
                best_score = score
                best = cand
        return best if best_score >= 0 else None

    def _merge_citations_into_refs(self, *, turn: Any, refs_by_key: Dict[Tuple[int, int, int], Dict[str, Any]]) -> Dict[str, int]:
        """Populate refs_by_key from turn.message.metadata.citations (fill-only-empty; skip invalid).
        Returns counts: {'examined','invalid','exact','tolerant','unmatched'}
        """
        meta = getattr(turn.message, 'metadata', None)
        if not meta:
            return {'examined': 0, 'invalid': 0, 'exact': 0, 'tolerant': 0, 'unmatched': 0}
        # Access citations list
        citations = []
        if hasattr(meta, 'citations') and getattr(meta, 'citations') is not None:
            citations = getattr(meta, 'citations')
        elif hasattr(meta, '__getitem__'):
            citations = meta.get('citations', [])
        # Merge
        examined = 0
        invalid = 0
        exact = 0
        tolerant = 0
        unmatched = 0
        for raw in citations or []:
            examined += 1
            entry = raw if isinstance(raw, dict) else (raw.dict() if hasattr(raw, 'dict') else {})
            if not entry:
                continue
            if entry.get('invalid_reason'):
                invalid += 1
                continue
            key = self.extract_key(entry, is_citation=True)
            if not key or key not in refs_by_key:
                # try tolerant matching against existing marker keys
                best_key = self._find_best_marker_key(entry_key=key, refs_by_key=refs_by_key)
                if not best_key:
                    unmatched += 1
                    continue
                key = best_key
                tolerant += 1
            else:
                exact += 1
            # Inline field collection for citations
            metadata = entry.get('metadata', {})
            extra = metadata.get('extra') or {}
            data = {
                'title': metadata.get('title', ''),
                'url': metadata.get('url', ''),
                'text': (metadata.get('text') or (extra.get('evidence_text') if isinstance(extra, dict) else '') or ''),
                'pub_date': metadata.get('pub_date'),
                'attribution': (metadata.get('source') or (extra.get('connector_source') if isinstance(extra, dict) else '') or ''),
            }
            self.fill_if_empty(refs_by_key[key], data)
            # Print CIT line if title present
            try:
                if (data.get('title') or '').strip():
                    ref_id, s, e = key
                    title = (data.get('title') or '').strip().replace('"', '""')
                    print(f'{int(ref_id)},{int(s)},{int(e)},"{title}"')
            except Exception:
                pass
        return {'examined': examined, 'invalid': invalid, 'exact': exact, 'tolerant': tolerant, 'unmatched': unmatched}

    def _merge_content_refs_into_refs(self, *, turn: Any, refs_by_key: Dict[Tuple[int, int, int], Dict[str, Any]]) -> Dict[str, int]:
        """Populate refs_by_key from turn.message.metadata.content_references (fill-only-empty; skip invalid).
        Returns counts: {'examined','invalid','exact','tolerant','unmatched'}
        """
        meta = getattr(turn.message, 'metadata', None)
        if not meta:
            return {'examined': 0, 'invalid': 0, 'exact': 0, 'tolerant': 0, 'unmatched': 0}
        content_refs = []
        if hasattr(meta, 'content_references') and getattr(meta, 'content_references') is not None:
            content_refs = getattr(meta, 'content_references')
        elif hasattr(meta, '__getitem__'):
            content_refs = meta.get('content_references', [])
        examined = 0
        invalid = 0
        exact = 0
        tolerant = 0
        unmatched = 0
        for raw in content_refs or []:
            examined += 1
            entry = raw if isinstance(raw, dict) else (raw.dict() if hasattr(raw, 'dict') else {})
            if not entry:
                continue
            if entry.get('invalid') is True:
                invalid += 1
                continue
            key = self.extract_key(entry, is_citation=False)
            if not key or key not in refs_by_key:
                # try tolerant matching against existing marker keys
                best_key = self._find_best_marker_key(entry_key=key, refs_by_key=refs_by_key)
                if not best_key:
                    unmatched += 1
                    continue
                key = best_key
                tolerant += 1
            else:
                exact += 1
            # Inline field collection for content_references
            data: Dict[str, Any] = {}
            grouped_webpages = entry.get('grouped_webpages', []) or []
            found = False
            for group in grouped_webpages:
                for item in (group.get('items', []) or []):
                    data = {
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'text': item.get('snippet', ''),
                        'pub_date': item.get('pub_date'),
                        'attribution': item.get('attribution', ''),
                    }
                    found = True
                    break
                if found:
                    break
            if not found:
                data = {
                    'title': entry.get('title', ''),
                    'url': entry.get('url', ''),
                    'text': entry.get('snippet', ''),
                    'pub_date': entry.get('pub_date'),
                    'attribution': entry.get('attribution', ''),
                }
            self.fill_if_empty(refs_by_key[key], data)
            # Print CR line if title present
            try:
                if (data.get('title') or '').strip():
                    ref_id, s, e = key
                    title = (data.get('title') or '').strip().replace('"', '""')
                    print(f'{int(ref_id)},{int(s)},{int(e)},"{title}"')
            except Exception:
                pass
        return {'examined': examined, 'invalid': invalid, 'exact': exact, 'tolerant': tolerant, 'unmatched': unmatched}
