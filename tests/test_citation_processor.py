import json
import re
from pathlib import Path
from typing import Any, Tuple

from extract_chat.context.document_context import DocumentContext
from extract_chat.processors.citation_processor import (
    CitationProcessor,
    _reference_identity_from_fields,
)
from extract_chat.schemas.conversation import Conversation

TURN_ID = "c3df4f37-ab12-4ab6-a810-6b687a759b83"
SAMPLE_PATH = Path("tmp/PA-Paper/chatgpt_convo_686ab2a1-6578-8003-b0e6-79b76323e002.json")
MARKER_PATTERN = re.compile(r"【(\d+)†L(\d+)-L(\d+)】")


def load_turn() -> Tuple[Conversation, Any]:
    raw = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    conversation = Conversation.model_validate(raw)
    turn = conversation.mapping[TURN_ID]
    return conversation, turn


def _identity_from_reference(ref: dict) -> tuple:
    return _reference_identity_from_fields(
        ref.get("url"),
        ref.get("title"),
        ref.get("text"),
        ref.get("ref_id", 0),
        ref.get("seq", 0),
        bool(ref.get("is_fallback")),
        ref.get("source_label"),
    )


def test_citation_processor_merges_metadata():
    conversation, turn = load_turn()
    DocumentContext.initialize(conversation=conversation)
    try:
        processor = CitationProcessor()
        seq_map = {}
        result, next_seq = processor.get_references_data(
            turn=turn,
            ref_turn_counter=1,
            start_seq=1,
            existing_sequences=seq_map,
        )
    finally:
        DocumentContext.reset()

    references = result["references"]
    assert references, "Expected references to be returned for the sample turn"

    identities = {}
    for ref in references:
        if ref.get("skip_citation"):
            continue
        identity = _identity_from_reference(ref)
        identities.setdefault(identity, ref["seq"])
        assert identities[identity] == ref["seq"], "References sharing identity should reuse the same sequence number"

    used_sequences = {int(ref["seq"]) for ref in references if not ref.get("skip_citation")}
    if used_sequences:
        assert next_seq >= max(used_sequences) + 1
    assert len(set(identities.values())) == len(identities)

    refs_by_key = {
        (ref["ref_id"], ref["start_line"], ref["end_line"]): ref
        for ref in references
        if not ref.get("skip_citation")
    }

    key = (18, 153, 161)
    assert key in refs_by_key, "Reference marker for citation 18 should be present"

    entry = refs_by_key[key]
    assert entry["turn_id"] == 1
    assert entry["unique_id"].startswith("1_")
    assert entry["title"] == (
        "The Impact of Parental Alienating Behaviours on the Mental Health of Adults "
        "Alienated in Childhood - PMC"
    )
    assert entry["url"].startswith("https://pmc.ncbi.nlm.nih.gov/articles/PMC9026878/")
    assert entry["attribution"] == "pmc.ncbi.nlm.nih.gov"

    metadata = turn.message.metadata
    citation_keys = set()
    for citation in metadata["citations"]:
        if citation.get("invalid_reason"):
            continue
        extra = citation["metadata"].get("extra", {})
        try:
            citation_keys.add(
                (
                    int(extra["cited_message_idx"]),
                    int(extra["start_line_num"]),
                    int(extra["end_line_num"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    content_keys = set()
    for content_ref in metadata["content_references"]:
        if content_ref.get("invalid"):
            continue
        match = MARKER_PATTERN.search(content_ref.get("matched_text", ""))
        if not match:
            continue
        content_keys.add(
            (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        )

    result_keys = set(refs_by_key.keys())
    assert citation_keys.issubset(result_keys)
    assert content_keys.issubset(result_keys)
