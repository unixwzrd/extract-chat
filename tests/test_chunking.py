from __future__ import annotations

from extract_chat.chunking import MAX_CHUNK_BYTES, ChunkOptions, ChunkingError, build_markdown_chunks
from extract_chat.naming import canonical_conversation_stem
from extract_chat.schemas.render_models import RenderDocument, RenderTurn


def _document(content: str, *, turns: int = 1) -> RenderDocument:
    return RenderDocument(
        title="Continuity Test",
        conversation_id="conversation-1",
        create_time=1_700_000_000,
        update_time=1_700_086_400,
        turns=[
            RenderTurn(role="user" if index % 2 == 0 else "assistant", turn_id=f"turn-{index}", content=content)
            for index in range(turns)
        ],
    )


def test_canonical_stem_uses_start_end_and_title() -> None:
    assert canonical_conversation_stem(_document("hello")) == "2023-11-14--2023-11-15--continuity-test"


def test_chunking_never_exceeds_512_kib() -> None:
    bundle = build_markdown_chunks(_document("αβγ " * 180_000), stem="continuity")
    assert len(bundle.chunks) > 1
    assert all(chunk.byte_count <= MAX_CHUNK_BYTES for chunk in bundle.chunks)
    assert all(len(chunk.text.encode("utf-8")) == chunk.byte_count for chunk in bundle.chunks)


def test_chunking_enforces_smaller_byte_and_line_limits() -> None:
    options = ChunkOptions(max_bytes=1_200, max_lines=18, overlap_turns=0)
    bundle = build_markdown_chunks(_document("paragraph\n\n" * 80, turns=4), stem="small", options=options)
    assert len(bundle.chunks) > 1
    assert all(chunk.byte_count <= 1_200 for chunk in bundle.chunks)
    assert all(chunk.line_count <= 18 for chunk in bundle.chunks)


def test_turn_strategy_rejects_oversized_turn() -> None:
    options = ChunkOptions(strategy="turn", max_bytes=400, overlap_turns=0)
    try:
        build_markdown_chunks(_document("too large " * 200), stem="turn", options=options)
    except ChunkingError as exc:
        assert "single turn" in str(exc)
    else:
        raise AssertionError("Expected oversized turn failure")


def test_overlap_is_marked_and_new_turns_are_unique() -> None:
    options = ChunkOptions(max_bytes=900, overlap_turns=1)
    bundle = build_markdown_chunks(_document("content " * 12, turns=8), stem="overlap", options=options)
    assert len(bundle.chunks) > 1
    flattened = [turn_id for chunk in bundle.chunks for turn_id in chunk.turn_ids]
    assert sorted(flattened) == [f"turn-{index}" for index in range(8)]
    assert any("## Overlapped Context" in chunk.text for chunk in bundle.chunks[1:])


def test_line_and_byte_overlap_are_supported() -> None:
    for options in (
        ChunkOptions(max_bytes=800, overlap_turns=0, overlap_lines=2),
        ChunkOptions(max_bytes=800, overlap_turns=0, overlap_bytes=40),
    ):
        bundle = build_markdown_chunks(_document("one\ntwo\nthree\nfour", turns=10), stem="overlap", options=options)
        assert len(bundle.chunks) > 1
        assert any("## Overlapped Context" in chunk.text for chunk in bundle.chunks[1:])
        assert all(chunk.byte_count <= options.max_bytes for chunk in bundle.chunks)
