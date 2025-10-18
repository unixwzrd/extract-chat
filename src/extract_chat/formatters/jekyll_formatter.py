from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from extract_chat.context.document_context import DocumentContext
from extract_chat.processors.reference_processing.citation_processor import (
    CitationProcessor,
)
from extract_chat.processors.reference_processing.reference_utils import (
    build_reference_payload,
    format_apa_reference_entry,
    replace_inline_citation_markers,
    strip_sources_and_references,
)


@dataclass
class JekyllPage:
    """Represents a single Jekyll-ready page."""

    title: str
    slug: str
    filename: str
    permalink: str
    content: str


class JekyllTurnExporter:
    """Export a single assistant turn into Jekyll-friendly section pages."""

    def __init__(self, *, base_slug: str, layout: str = "page") -> None:
        self.base_slug = _slugify(base_slug)
        self.layout = layout

    def _clean_text_for_jekyll(self, text: str) -> str:
        """
        Clean text specifically for Jekyll output using UnicodeFix.
        
        This is more aggressive than the base text normalization
        because Jekyll is sensitive to certain Unicode characters.
        """
        if not text:
            return ""
        
        # Use UnicodeFix for aggressive Unicode cleanup
        try:
            from unicodefix.transforms import clean_text
            text = clean_text(text, preserve_invisible=False, preserve_quotes=True, preserve_dashes=True)
        except ImportError:
            # Fallback if unicodefix is not available
            pass
        
        return text

    def export_turn(
        self,
        *,
        conversation,
        turn_id: str,
        reference_page_title: str = "References",
        audit_dir: Path | None = None,
    ) -> tuple[List[JekyllPage], JekyllPage]:
        """Return a list of section pages and a references page for the given turn."""

        ctx = DocumentContext.get()
        if ctx is None:
            raise RuntimeError("DocumentContext must be initialized before exporting")

        turn = conversation.mapping[turn_id]
        message = turn.message

        processor = CitationProcessor()
        references_table, _ = processor.get_references_data(
            turn=turn,
            ref_turn_counter=1,
            start_seq=1,
            existing_sequences={},
        )

        raw_content = ctx.extract_text_from_message(message)
        processed_content = replace_inline_citation_markers(
            raw_content,
            references_table.get("references", []),
        )

        processed_content = _rewrite_reference_links(
            processed_content,
            base_slug=self.base_slug,
        )
        processed_content, sources_block = strip_sources_and_references(processed_content)

        sections = _split_sections(processed_content)

        if not sections:
            raise ValueError("No sections found in assistant turn content")

        section_pages: List[JekyllPage] = []
        occurrence_links: Dict[str, str] = {}

        for index, section in enumerate(sections, start=1):
            section_slug = _slugify(section.heading)
            occurrence_ids = set(_find_occurrence_ids(section.body))
            for uid in occurrence_ids:
                occurrence_links[uid] = section_slug

            permalink = f"/{self.base_slug}-{section_slug}.html"
            front_matter = _build_front_matter(
                title=section.heading,
                permalink=permalink,
                layout=self.layout,
                nav_order=index,
            )
            full_content = front_matter + section.rendered_body
            filename = f"{self.base_slug}-{section_slug}.md"
            section_pages.append(
                JekyllPage(
                    title=section.heading,
                    slug=section_slug,
                    filename=filename,
                    permalink=permalink,
                    content=full_content,
                )
            )

        references_page, reference_groups = self._build_references_page(
            references_table.get("references", []),
            occurrence_links,
            section_count=len(section_pages),
            title=reference_page_title,
        )

        _write_reference_audit(
            sources_block=sources_block,
            references=references_table.get("references", []),
            groups=reference_groups,
            base_slug=self.base_slug,
            output_dir=audit_dir,
        )

        return section_pages, references_page

    def _build_references_page(
        self,
        references: Sequence[dict],
        occurrence_links: Dict[str, str],
        section_count: int,
        *,
        title: str,
    ) -> tuple[JekyllPage, List[Dict]]:
        blocks = [
            {
                "type": "assistant",
                "references_table": {"references": references},
                "metadata": {"reference_turn_number": 1},
            }
        ]
        payload = build_reference_payload(
            blocks,
            occurrence_filter=lambda occ: bool(
                occ.get("unique_id") and occurrence_links.get(occ.get("unique_id"))
            ),
        )
        groups = payload["groups"]

        lines: List[str] = ["## References", ""]

        for group in groups:
            meta = group.get("meta") or {}
            occurrences = [
                occ
                for occ in group.get("occurrences") or []
                if not occ.get("skip_citation")
            ]
            if not occurrences:
                continue

            anchors = " ".join(
                f'<a id="ref-target-{occ.get("unique_id")}"></a>'
                for occ in occurrences
                if occ.get("unique_id")
            )

            seq = _coerce_int(meta.get("seq"), default=0)
            if seq <= 0 and occurrences:
                seq = _coerce_int(occurrences[0].get("seq"), default=0)

            apa_entry = format_apa_reference_entry(meta, html=False)

            snippet = ""
            if not meta.get("is_fallback"):
                text = (meta.get("text") or "").strip().replace("\n", " ")
                if text:
                    # Clean text for Jekyll using UnicodeFix
                    text = self._clean_text_for_jekyll(text)
                    snippet = f'"{text}"'

            backlinks: List[str] = []
            for occ in occurrences:
                uid = occ.get("unique_id")
                if not uid:
                    continue
                slug = occurrence_links.get(uid)
                if not slug:
                    continue
                label = (occ.get("backlink_label") or "").strip()
                if not label:
                    continue
                backlinks.append(
                    f"[{label}^]({self.base_slug}-{slug}.md#ref-source-{uid})"
                )

            entry_parts: List[str] = []
            if anchors:
                entry_parts.append(anchors)

            entry_line = f"- Ref {seq}. {apa_entry}" if seq else f"- {apa_entry}"
            if snippet:
                entry_line = f"{entry_line} {snippet}"
            if backlinks:
                entry_line = f"{entry_line} {', '.join(backlinks)}"
            entry_parts.append(entry_line)

            lines.append(" ".join(entry_parts).strip())
            lines.append("")

        markdown = "\n".join(lines).strip() + "\n"

        references_permalink = f"/{self.base_slug}-references.html"
        front_matter = _build_front_matter(
            title=title,
            permalink=references_permalink,
            layout=self.layout,
            nav_order=section_count + 1,
        )
        filename = f"{self.base_slug}-references.md"
        return JekyllPage(
            title=title,
            slug="references",
            filename=filename,
            permalink=references_permalink,
            content=front_matter + markdown,
        ), groups


@dataclass
class _Section:
    heading: str
    body: str

    @property
    def rendered_body(self) -> str:
        heading_line = f"## {self.heading}\n\n"
        body = self.body.strip()
        return f"{heading_line}{body}\n" if body else heading_line


def _slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-") or "section"


def _rewrite_reference_links(text: str, *, base_slug: str) -> str:
    refs_url = f"{base_slug}-references"
    return re.sub(
        r'href="#(ref-target-[^"]+)"',
        lambda m: f'href="{refs_url}.md#{m.group(1)}"',
        text,
    )


def _parse_sources_block(sources_block: str) -> List[Dict[str, Any]]:
    if not sources_block:
        return []
    entries: List[Dict[str, Any]] = []
    entry_pattern = re.compile(r"^\s*(\d+)\.\s*(.*?)(?=\n\s*\d+\.\s*|$)", re.S | re.M)
    marker_pattern = re.compile(r"【(\d+)†L(\d+)-L(\d+)】")
    uid_pattern = re.compile(r"ref-source-([A-Za-z0-9_]+)")
    for match in entry_pattern.finditer(sources_block.strip()):
        index = int(match.group(1))
        body = match.group(2).strip()
        markers: List[Tuple[int, int, int]] = []
        for marker in marker_pattern.finditer(body):
            markers.append(
                (int(marker.group(1)), int(marker.group(2)), int(marker.group(3)))
            )
        unique_ids = uid_pattern.findall(body)
        clean_text = marker_pattern.sub("", body)
        clean_text = re.sub(r"<sup[^>]*>.*?</sup>", "", clean_text)
        clean_text = re.sub(r"</?a[^>]*>", "", clean_text)
        clean_text = re.sub(r"<[^>]+>", "", clean_text).strip()
        entries.append(
            {
                "index": index,
                "raw_text": body,
                "clean_text": clean_text,
                "markers": markers,
                "unique_ids": unique_ids,
            }
        )
    return entries


def _format_marker(marker: Tuple[int, int, int]) -> str:
    ref_id, start, end = marker
    return f"【{ref_id}†L{start}-L{end}】"


def _write_reference_audit(
    *,
    sources_block: str,
    references: Sequence[Dict[str, Any]],
    groups: List[Dict[str, Any]],
    base_slug: str,
    output_dir: Path | None = None,
) -> None:
    sources = _parse_sources_block(sources_block)
    if not sources:
        return

    marker_map: Dict[Tuple[int, int, int], set[int]] = {}
    unique_id_map: Dict[str, int] = {}
    for ref in references or []:
        if ref.get("skip_citation"):
            continue
        try:
            seq = int(ref.get("seq", 0))
            ref_id = int(ref.get("ref_id", 0))
            start = int(ref.get("start_line", 0))
            end = int(ref.get("end_line", 0))
        except (TypeError, ValueError):
            continue
        if seq <= 0:
            continue
        marker_map.setdefault((ref_id, start, end), set()).add(seq)
        uid = ref.get("unique_id")
        if isinstance(uid, str) and uid:
            unique_id_map.setdefault(uid, seq)

    seq_to_meta: Dict[int, Dict[str, Any]] = {}
    for group in groups:
        meta = group.get("meta") or {}
        seq = meta.get("seq")
        try:
            seq_int = int(seq)
        except (TypeError, ValueError):
            seq_int = 0
        if seq_int <= 0:
            occs = group.get("occurrences") or []
            for occ in occs:
                try:
                    seq_int = int(occ.get("seq", 0))
                except (TypeError, ValueError):
                    seq_int = 0
                if seq_int > 0:
                    break
        if seq_int > 0:
            seq_to_meta.setdefault(seq_int, meta)

    audit_entries: List[Dict[str, Any]] = []
    seq_to_source_indexes: Dict[int, List[int]] = {}

    for entry in sources:
        resolved_seqs: set[int] = set()
        unmatched_markers: List[Tuple[int, int, int]] = []
        for marker in entry["markers"]:
            seqs = marker_map.get(marker)
            if seqs:
                resolved_seqs.update(seqs)
            else:
                unmatched_markers.append(marker)
        for uid in entry.get("unique_ids", []):
            seq = unique_id_map.get(uid)
            if seq:
                resolved_seqs.add(seq)

        resolved_list = sorted(resolved_seqs)
        for seq in resolved_list:
            seq_to_source_indexes.setdefault(seq, []).append(entry["index"])

        audit_entries.append(
            {
                "index": entry["index"],
                "clean_text": entry["clean_text"],
                "raw_text": entry["raw_text"],
                "markers": entry["markers"],
                "resolved_seqs": resolved_list,
                "unmatched_markers": unmatched_markers,
            }
        )

    duplicate_refs = {
        seq: sorted(indexes)
        for seq, indexes in seq_to_source_indexes.items()
        if len(set(indexes)) > 1
    }

    total_sources = len(sources)
    unresolved_count = sum(1 for entry in audit_entries if not entry["resolved_seqs"])

    lines: List[str] = [
        f"# Reference Audit for {base_slug}",
        "",
        "Generated from the assistant-provided **Sources** block and cross-referenced ",
        "with canonical references resolved from metadata.",
        "",
        "## Summary",
        f"- Total source entries: {total_sources}",
        f"- Matched to canonical references: {total_sources - unresolved_count}",
        f"- Unmatched entries: {unresolved_count}",
    ]

    if duplicate_refs:
        dup_parts = [
            f"Ref {seq} (sources {', '.join(str(idx) for idx in indexes)})"
            for seq, indexes in sorted(duplicate_refs.items())
        ]
        lines.append(f"- Shared canonical references: {', '.join(dup_parts)}")
    lines.append("")
    lines.append("## Entries")
    lines.append("")

    for entry in sorted(audit_entries, key=lambda e: e["index"]):
        lines.append(f"### Source {entry['index']}")
        lines.append(entry["clean_text"] or entry["raw_text"])
        lines.append("")
        if entry["resolved_seqs"]:
            lines.append("Matched references:")
            for seq in entry["resolved_seqs"]:
                meta = seq_to_meta.get(seq, {})
                title = (meta.get("reference_title") or meta.get("title") or "").strip()
                url = (meta.get("url") or "").strip()
                if url:
                    lines.append(f"- Ref {seq}: {title} ({url})".strip())
                else:
                    lines.append(f"- Ref {seq}: {title or '<missing title>'}")
        else:
            lines.append("_No matching reference found in metadata._")

        if entry["unmatched_markers"]:
            lines.append(
                "Markers without matches: "
                + ", ".join(_format_marker(marker) for marker in entry["unmatched_markers"])
            )

        shared = [
            seq
            for seq in entry["resolved_seqs"]
            if len(seq_to_source_indexes.get(seq, [])) > 1
        ]
        if shared:
            lines.append(
                "Shares canonical references with other sources: "
                + ", ".join(f"Ref {seq}" for seq in shared)
            )
        lines.append("")

    if output_dir is None:
        audit_path = Path("tmp") / f"{base_slug}-reference-audit.md"
    else:
        audit_path = output_dir / f"{base_slug}-reference-audit.md"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _split_sections(text: str) -> List[_Section]:
    pattern = re.compile(r"(?m)^##\s+(.*)")
    matches = list(pattern.finditer(text))
    sections: List[_Section] = []
    for idx, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append(_Section(heading=heading, body=body))
    return sections


def _find_occurrence_ids(text: str) -> List[str]:
    return re.findall(r'id="ref-source-([^"]+)"', text)


def _build_front_matter(
    *, title: str, permalink: str, layout: str, nav_order: int
) -> str:
    front_matter = [
        "---",
        f"layout: {layout}",
        f"title: \"{title}\"",
        f"permalink: {permalink}",
        f"nav_order: {nav_order}",
        "---",
        "",
    ]
    return "\n".join(front_matter)


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
