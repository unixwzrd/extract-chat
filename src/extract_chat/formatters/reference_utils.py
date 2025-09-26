from __future__ import annotations

import re
from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any, Deque, Dict, List

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

    grouped_list.sort(key=_reference_sort_key)
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
        fallback_text = (info.get("title") or info.get("text") or '').strip()
        url = (info.get("url") or '').strip()
        if html and url:
            return f"<a href=\"{url}\">{fallback_text}</a>"
        if not html and url:
            return f"[{fallback_text}]({url})"
        return fallback_text

    raw_title = (info.get("title") or "").strip()
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
    year_fragment = f"({year})." if year else "(n.d.)."

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
        info.get("title"),
        info.get("text"),
        ref_id,
        seq,
        bool(info.get("is_fallback")),
        info.get("source_label"),
    )


def _score_reference_entry(entry: Mapping[str, Any]) -> int:
    score = 0
    if (entry.get("title") or "").strip():
        score += 4
    if (entry.get("url") or "").strip():
        score += 3
    if (entry.get("text") or "").strip():
        score += 2
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


def _reference_identity_key(
    url: Any,
    title: Any,
    text: Any,
    ref_id: int,
    seq: int,
    is_fallback: bool = False,
    source_label: Any = "",
) -> tuple:
    url_norm = _normalize_url(url)
    base_url = url_norm.split('#', 1)[0] if url_norm else ''
    title_norm = _normalize_text(title)
    text_norm = _normalize_text(text)
    if is_fallback and not title_norm:
        title_norm = text_norm
    label_norm = _normalize_text(source_label)
    identity_text = title_norm or text_norm or ''
    if label_norm and label_norm != identity_text:
        identity_text = f"{identity_text}::{label_norm}" if identity_text else label_norm
    if base_url or identity_text:
        return (base_url, identity_text)
    return (ref_id, seq)
