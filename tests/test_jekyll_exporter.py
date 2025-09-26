import json
import re
from pathlib import Path

import pytest

from extract_chat.context.document_context import DocumentContext
from extract_chat.formatters.jekyll_exporter import JekyllTurnExporter
from extract_chat.schemas.conversation import Conversation

SAMPLE_PATH = Path("tmp/PA-Paper/chatgpt_convo_686ab2a1-6578-8003-b0e6-79b76323e002.json")
TURN_ID = "c3df4f37-ab12-4ab6-a810-6b687a759b83"


@pytest.fixture(scope="module")
def conversation() -> Conversation:
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    return Conversation.model_validate(data)


def test_exporter_builds_sections_and_references(conversation: Conversation, tmp_path):
    DocumentContext.initialize(conversation=conversation)
    try:
        exporter = JekyllTurnExporter(base_slug="2025-09-25-pa-paper")
        sections, references_page = exporter.export_turn(
            conversation=conversation,
            turn_id=TURN_ID,
            reference_page_title="References",
        )
    finally:
        DocumentContext.reset()

    assert sections, "Expected at least one section page"
    assert references_page.slug == "references"

    section_links = {}
    for section in sections:
        assert section.filename.startswith("2025-09-25-pa-paper-")
        assert section.content.startswith("---\n")
        assert f"{exporter.base_slug}-references.html" in section.content
        ids = set(re.findall(r'id="ref-source-([^"]+)"', section.content))
        for uid in ids:
            section_links[uid] = section.filename.replace(".md", ".html")

    assert section_links, "Expected reference anchors inside section pages"

    # Ensure the last section preserves the Sources block
    assert "**Sources:**" in sections[-1].content

    # References page should link back to each section anchor
    for uid, html_name in section_links.items():
        expected_backlink = f"{html_name}#ref-source-{uid}"
        assert expected_backlink in references_page.content

    # Inline citations point to the references page
    assert all(
        f"{exporter.base_slug}-references.html" in match
        for match in re.findall(r'href="([^"]+references\.html#[^"]+)"', "\n".join(p.content for p in sections))
    )
