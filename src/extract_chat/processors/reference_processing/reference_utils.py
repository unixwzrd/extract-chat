from __future__ import annotations

import re
from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any, Deque, Dict, List

SHORT_SNIPPET_WORD_LIMIT = 2

__all__ = [
    "extract_reference_groups",
    "generate_backlink_labels",
    "replace_inline_citation_markers",
    "format_apa_reference_entry",
]


def extract_reference_groups(conversation_blocks: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate reference occurrences across assistant content blocks."""
    groups: Dict[tuple, Dict[str, Any]] = {}

    for block in conversation_blocks:
        if block.get("type") != "assistant":
            continue
        refs_block = block.get("references_table") or {}
        refs_list = refs_block.get("references") or []
        turn_num = block.get("metadata", {}).get("reference_turn_number")
        if not refs_list or turn_num is None:
            continue
        for entry in refs_list:
            ref_id_raw = entry.get("ref_id")
            if ref_id_raw is None:
                continue
            try:
                ref_id_int = int(ref_id_raw)
            except (TypeError, ValueError):
                continue
            enriched_entry = dict(entry)
            if enriched_entry.get("skip_citation"):
                continue
            try:
                enriched_entry["turn_num"] = int(turn_num)
            except (TypeError, ValueError):
                enriched_entry["turn_num"] = turn_num
            identity = _reference_identity_from_dict(enriched_entry)
            group = groups.setdefault(
                identity,
                {
                    "ref_id": ref_id_int,
                    "entries": [],
                    "meta": None,
                    "best_score": -1,
                    "min_seq": float("inf"),
                },
            )
            group["entries"].append(enriched_entry)
            score = _score_reference_entry(enriched_entry)
            if score > group["best_score"]:
                group["meta"] = enriched_entry
                group["best_score"] = score
            try:
                seq_val = int(enriched_entry.get("seq", 10**9))
            except (TypeError, ValueError):
                seq_val = 10**9
            if seq_val < group["min_seq"]:
                group["min_seq"] = seq_val

    grouped_list: List[Dict[str, Any]] = []
    for group in groups.values():
        entries = sorted(group["entries"], key=lambda e: int(e.get("seq", 10**9)))
        if not entries:
            continue
        meta = group.get("meta") or entries[0]
        grouped_list.append(
            {
                "ref_id": group["ref_id"],
                "meta": meta,
                "occurrences": entries,
                "min_seq": group.get("min_seq", 10**9),
            }
        )

    grouped_list = _merge_groups_by_base_url(grouped_list)
    grouped_list.sort(key=_reference_sort_key)
    _renumber_group_sequences(grouped_list, refs_list)
    return grouped_list


def generate_backlink_labels(count: int) -> List[str]:
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


def replace_inline_citation_markers(
    text: str,
    references: Sequence[Mapping[str, Any]],
) -> str:
    """Replace inline markers like ```` with cite superscripts."""
    if not text or not references:
        return text

    queue_by_key: Dict[tuple[int, int, int], Deque[tuple[int, Any, str]]] = {}
    suppressed_keys: set[tuple[int, int, int]] = set()

    seen_seq_order: List[int] = []
    for ref in references:
        if ref.get("skip_citation"):
            continue
        try:
            seq_val = int(ref.get("seq"))
        except (TypeError, ValueError):
            continue
        if seq_val not in seen_seq_order:
            seen_seq_order.append(seq_val)
    seq_map = {orig: idx + 1 for idx, orig in enumerate(sorted(seen_seq_order))}

    for ref in references:
        try:
            ref_id = int(ref.get("ref_id"))
            start = int(ref.get("start_line"))
            end = int(ref.get("end_line"))
            seq_orig = int(ref.get("seq"))
        except (TypeError, ValueError):
            continue
        unique_id = ref.get("unique_id")
        label = (ref.get("occurrence_label") or "").strip()
        if ref.get("skip_citation"):
            suppressed_keys.add((ref_id, start, end))
            continue
        seq_value = seq_map.get(seq_orig, seq_orig)
        ref["seq"] = seq_value
        queue = queue_by_key.setdefault((ref_id, start, end), deque())
        queue.append((seq_value, unique_id, label))

    if not queue_by_key and not suppressed_keys:
        return text

    pattern = r"【(\d+)†L(\d+)-L(\d+)】"

    last_key: tuple[int, int, int] | None = None
    last_seq: int | None = None
    last_pos: int | None = None

    def _emit_anchor(unique_id: str | None) -> str:
        if not unique_id:
            return ""
        return f'<a id="ref-source-{unique_id}"></a>'

    def _emit_sup(seq: int, unique_id: str | None) -> str:
        if not unique_id:
            return f'<sup>{seq}</sup>'
        return f'<sup id="ref-source-{unique_id}"><a href="#ref-target-{unique_id}">{seq}</a></sup>'

    def _repl(match: re.Match[str]) -> str:
        nonlocal last_key, last_seq, last_pos
        ref_id = int(match.group(1))
        start_line = int(match.group(2))
        end_line = int(match.group(3))
        key = (ref_id, start_line, end_line)
        queue = queue_by_key.get(key)
        if not queue:
            if key in suppressed_keys:
                return ""
            return match.group(0)
        seq, unique_id, label = queue.popleft()
        if last_key and last_key[0] == ref_id and abs(start_line - last_key[1]) <= 3 and abs(end_line - last_key[2]) <= 3:
            return _emit_anchor(unique_id)
        if last_seq is not None and seq == last_seq and last_pos is not None and match.start() - last_pos < 50:
            last_key = key
            return _emit_anchor(unique_id)
        last_key = key
        last_seq = seq
        last_pos = match.start()
        return _emit_sup(seq, unique_id)

    try:
        result = re.sub(pattern, _repl, text)
    except re.error:
        return text
    # Insert comma while keeping it inside the superscript when adjacent citations appear
    result = re.sub(r'</a></sup>\s*(?=<sup)', r'</a>,</sup> ', result)
    return result


def format_apa_reference_entry(info: Mapping[str, Any], html: bool) -> str:
    """Generate a lightweight APA-style reference string."""
    if info.get("is_fallback"):
        fallback_text = (info.get("reference_title") or info.get("title") or info.get("text") or '').strip()
        url = (info.get("url") or '').strip()
        if html and url:
            return f"<a href=\"{url}\">{fallback_text}</a>"
        if not html and url:
            return f"[{fallback_text}]({url})"
        return fallback_text

    # Use reference_title if available, otherwise fall back to title
    raw_title = (info.get("reference_title") or info.get("title") or "").strip()
    if not raw_title:
        raw_title = (info.get("text") or "").strip()
    if not raw_title:
        raw_title = (info.get("url") or "").strip()
    title = raw_title or "Untitled source"
    if title == "Untitled source":
        ref_id = info.get("ref_id")
        turn_num = info.get("turn_num")
        if ref_id is not None:
            if turn_num is not None:
                title = f"Reference {ref_id} (Turn {turn_num})"
            else:
                title = f"Reference {ref_id}"

    url = (info.get("url") or "").strip()
    pub_date = info.get("pub_date")
    year = _extract_year(pub_date)
    year_fragment = f"({year})." if year else ""

    # Escape pipe characters in reference titles to prevent Jekyll table interpretation
    title = title.replace('|', '\\|')

    placeholder = title.startswith("Metadata missing for ref_id")
    if html:
        if url:
            title_fmt = f"<a href=\"{url}\"><em>{title}</em></a>"
        elif not placeholder:
            title_fmt = f"<em>{title}</em>"
        else:
            title_fmt = title
    else:
        if url:
            title_fmt = f"[*{title}*]({url})"
        elif not placeholder:
            title_fmt = f"*{title}*"
        else:
            title_fmt = title

    parts = [year_fragment, title_fmt]
    return " ".join(p.strip() for p in parts if p).strip()


def _reference_identity_from_dict(info: Mapping[str, Any]) -> tuple:
    ref_id = int(info.get("ref_id", 0))
    seq = int(info.get("seq", 0))
    return _reference_identity_key(
        info.get("url"),
        info.get("reference_title") or info.get("title"),
        info.get("text"),
        ref_id,
        seq,
        bool(info.get("is_fallback")),
        info.get("source_label"),
        info.get("attribution"),
        (info.get("start_line"), info.get("end_line")),
    )


def _score_reference_entry(entry: Mapping[str, Any]) -> int:
    score = 0
    title = (entry.get("title") or "").strip()
    url = (entry.get("url") or "").strip()
    text = (entry.get("text") or "").strip()
    if title:
        score += 4
    if url:
        score += 3
    if text:
        score += 2 + min(5, len(re.findall(r"\b\w+\b", text)))
    if entry.get("attribution"):
        score += 1
    return score


def _reference_sort_key(group: Dict[str, Any]) -> tuple[int, int]:
    return group.get("min_seq", 10**9), group.get("ref_id", 10**9)


def _extract_year(value: Any) -> str | None:
    if not value:
        return None
    try:
        match = re.search(r"(\d{4})", str(value))
    except re.error:
        return None
    if match:
        return match.group(1)
    return None


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
    return value.lower().rstrip('/')


def _normalize_text(text: Any) -> str:
    return _clean_str(text).lower()


def _merge_groups_by_base_url(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge groups using two-step logic:
    1. First group by reference_title (handles different articles from same domain)
    2. Then merge groups with same base URL and short text snippets (handles LinkedIn-type cases)
    """
    if not groups:
        return groups

    # Step 1: Group by reference_title first, but also consider text content
    initial_groups = {}
    for group in groups:
        meta = group.get("meta") or {}
        ref_title = meta.get("reference_title", "") or meta.get("title", "")
        if ref_title:
            # Include first few words of text to distinguish different parts of same article
            text = meta.get("text", "")
            text_preview = ' '.join(text.split()[:5]) if text else ''
            group_key = f"title:{ref_title}|text:{text_preview}"
        else:
            # Fallback to URL if no title
            url = meta.get("url", "")
            base_url = _get_base_url(url)
            group_key = f"url:{base_url}" if base_url else f"fallback:{id(group)}"
        
        if group_key not in initial_groups:
            initial_groups[group_key] = []
        initial_groups[group_key].append(group)
    
    # Step 2: Merge groups with same base URL and short text snippets
    merged_groups = {}
    base_url_to_groups = {}
    
    for group_key, group_list in initial_groups.items():
        if not group_list:
            continue
            
        # Get base URL and text snippet info from first group
        first_group = group_list[0]
        meta = first_group.get("meta") or {}
        url = meta.get("url", "")
        base_url = _get_base_url(url)
        text = meta.get("text", "")
        
        # If base_url exists and text is short (like LinkedIn), group by base_url
        # Use string length instead of word count for better performance
        if base_url and len(text) <= 200:  # Short snippet threshold (200 chars)
            if base_url not in base_url_to_groups:
                base_url_to_groups[base_url] = []
            base_url_to_groups[base_url].extend(group_list)
        else:
            # Keep original grouping
            merged_groups[group_key] = group_list
    
    # Add merged base URL groups
    for base_url, all_groups in base_url_to_groups.items():
        merged_groups[f"merged_url:{base_url}"] = all_groups
    
    # Convert back to list format
    final_groups = []
    for group_list in merged_groups.values():
        if len(group_list) == 1:
            final_groups.append(group_list[0])
        else:
            # Merge multiple groups into one
            final_groups.append(_combine_reference_group_cluster(group_list))
    
    return final_groups


def _combine_reference_group_cluster(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not groups:
        raise ValueError("Expected at least one group to combine")

    best = max(
        groups,
        key=lambda g: (
            _snippet_word_count((g.get("meta") or {}).get("text")),
            _score_reference_entry(g.get("meta") or {}),
            -g.get("min_seq", 10**9),
        ),
    )

    combined_occurrences: List[Dict[str, Any]] = []
    min_seq = 10**9
    for group in groups:
        combined_occurrences.extend(group.get("occurrences", []))
        min_seq = min(min_seq, group.get("min_seq", 10**9))

    best_meta = dict(best.get("meta") or {})
    occ_min_seq = min(
        (int(occ.get("seq", 10**9)) for occ in combined_occurrences),
        default=min_seq,
    )
    if occ_min_seq != 10**9:
        best_meta["seq"] = occ_min_seq

    return {
        "ref_id": best.get("ref_id"),
        "meta": best_meta,
        "occurrences": combined_occurrences,
        "min_seq": min_seq,
    }


def _merge_two_groups(primary: Dict[str, Any], secondary: Dict[str, Any]) -> Dict[str, Any]:
    combined_occurrences = primary.get("occurrences", []) + secondary.get("occurrences", [])
    min_seq = min(primary.get("min_seq", 10**9), secondary.get("min_seq", 10**9))
    best = primary
    other_text_len = _snippet_word_count((secondary.get("meta") or {}).get("text"))
    best_text_len = _snippet_word_count((best.get("meta") or {}).get("text"))
    if other_text_len > best_text_len:
        best = secondary
    best_meta = dict(best.get("meta") or {})
    occ_min_seq = min(
        (int(occ.get("seq", 10**9)) for occ in combined_occurrences),
        default=min_seq,
    )
    if occ_min_seq != 10**9:
        best_meta["seq"] = occ_min_seq
    return {
        "ref_id": best.get("ref_id"),
        "meta": best_meta,
        "occurrences": combined_occurrences,
        "min_seq": min_seq,
    }


def _snippet_word_count(text: Any) -> int:
    if not text:
        return 0
    return len(re.findall(r"\b\w+\b", str(text)))


def _normalize_snippet(text: Any) -> str:
    if not text:
        return ""
    normalized = re.sub(r"\s+", " ", str(text).strip().lower())
    return normalized


def _get_base_url(url: str) -> str:
    """Extract base URL without fragments or query parameters."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return ""


def _snippets_should_merge(group_a: Dict[str, Any], group_b: Dict[str, Any]) -> bool:
    meta_a = group_a.get("meta") or {}
    meta_b = group_b.get("meta") or {}
    text_a = meta_a.get("text") or ""
    text_b = meta_b.get("text") or ""
    count_a = _snippet_word_count(text_a)
    count_b = _snippet_word_count(text_b)

    if not text_a or not text_b:
        return True
    if count_a <= SHORT_SNIPPET_WORD_LIMIT or count_b <= SHORT_SNIPPET_WORD_LIMIT:
        return True

    norm_a = _normalize_snippet(text_a)
    norm_b = _normalize_snippet(text_b)
    if not norm_a or not norm_b:
        return True
    if norm_a == norm_b:
        return True
    if norm_a in norm_b or norm_b in norm_a:
        return True

    return False


def _renumber_group_sequences(
    groups: List[Dict[str, Any]],
    original_refs: Sequence[Mapping[str, Any]],
) -> None:
    uid_to_original: Dict[str, Mapping[str, Any]] = {}
    for ref in original_refs:
        uid = ref.get("unique_id")
        if isinstance(uid, str):
            uid_to_original[uid] = ref

    for idx, group in enumerate(groups, start=1):
        meta = group.get("meta") or {}
        meta["seq"] = idx
        for occ in group.get("occurrences", []):
            occ["seq"] = idx
            uid = occ.get("unique_id")
            if isinstance(uid, str) and uid in uid_to_original:
                uid_to_original[uid]["seq"] = idx


def _reference_identity_key(
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
    title_norm = _normalize_text(title)
    text_norm = _normalize_text(text)
    if is_fallback and not title_norm:
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
