from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence

from extract_chat.context.document_context import DocumentContext
from extract_chat.processors.reference_processing.citation_processor import (
    CitationProcessor,
)
from extract_chat.processors.reference_processing.reference_utils import (
    extract_reference_groups,
    format_apa_reference_entry,
    generate_backlink_labels,
    replace_inline_citation_markers,
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
        processed_content, sources_block = _strip_sources_and_references(processed_content)

        sections = _split_sections(processed_content)

        if not sections:
            raise ValueError("No sections found in assistant turn content")

        if sources_block and sections:
            sections[-1].body = (sections[-1].body + "\n\n" + sources_block.strip()).strip()

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

        references_page = self._build_references_page(
            references_table.get("references", []),
            occurrence_links,
            section_count=len(section_pages),
            title=reference_page_title,
        )

        return section_pages, references_page

    def _build_references_page(
        self,
        references: Sequence[dict],
        occurrence_links: Dict[str, str],
        section_count: int,
        *,
        title: str,
    ) -> JekyllPage:
        blocks = [
            {
                "type": "assistant",
                "references_table": {"references": references},
                "metadata": {"reference_turn_number": 1},
            }
        ]
        groups = extract_reference_groups(blocks)

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

            backlink_labels = generate_backlink_labels(len(occurrences))
            backlinks: List[str] = []
            for idx, occ in enumerate(occurrences):
                uid = occ.get("unique_id")
                if not uid:
                    continue
                slug = occurrence_links.get(uid)
                if not slug:
                    continue
                label = (occ.get("occurrence_label") or "").strip() or backlink_labels[idx]
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
        )


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


def _strip_sources_and_references(text: str) -> tuple[str, str]:
    sources_block = ""
    pattern = re.compile(r"\*\*Sources:\*\*.*?(?=## References|\Z)", re.S)
    match = pattern.search(text)
    if match:
        sources_block = match.group(0).strip()
        text = text[: match.start()] + text[match.end():]
    text = text.rstrip()
    if "## References" in text:
        text = text.split("## References", 1)[0].rstrip()
    return text, sources_block


def _rewrite_reference_links(text: str, *, base_slug: str) -> str:
    refs_url = f"{base_slug}-references"
    return re.sub(
        r'href="#(ref-target-[^"]+)"',
        lambda m: f'href="{refs_url}.md#{m.group(1)}"',
        text,
    )


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

