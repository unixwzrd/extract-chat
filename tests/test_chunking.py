from __future__ import annotations

from extract_chat.chunking import MAX_CHUNK_BYTES, ChunkOptions, ChunkingError, build_markdown_chunks, write_chunk_bundle
from extract_chat.naming import canonical_conversation_stem
from extract_chat.schemas.render_models import MediaItem, RenderDocument, RenderTurn


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


def test_context_move_instructions_match_chunk_bundle(tmp_path) -> None:
    options = ChunkOptions(
        strategy="hybrid",
        max_bytes=800,
        overlap_turns=0,
        overlap_lines=2,
        upload_batch_size=1,
    )
    bundle = build_markdown_chunks(_document("one\ntwo\nthree\nfour", turns=10), stem="handoff", options=options)

    assert len(bundle.chunks) > 1
    assert f"Numbered conversation chunks: {len(bundle.chunks)}" in bundle.instructions_text
    assert "Boundary strategy: `hybrid`" in bundle.instructions_text
    assert "Continuity overlap: up to 2 prior lines" in bundle.instructions_text
    assert "up to 1 conversation chunk per batch" in bundle.instructions_text
    assert "Treat the uploaded transcript as historical reference material" in bundle.instructions_text
    assert "Do not summarize the transcript back to me" in bundle.instructions_text
    assert bundle.manifest["handoff"]["upload_batch_size"] == 1
    assert bundle.manifest["handoff"]["batch_count"] == len(bundle.chunks)

    paths = write_chunk_bundle(bundle, tmp_path / "chunks")
    instructions_path = tmp_path / "chunks" / "context-move-instructions.md"
    assert instructions_path in paths
    assert instructions_path.read_text(encoding="utf-8") == bundle.instructions_text


def test_context_move_instructions_describe_no_overlap() -> None:
    options = ChunkOptions(max_bytes=800, overlap_turns=0)
    bundle = build_markdown_chunks(_document("content " * 12, turns=3), stem="no-overlap", options=options)

    assert "Continuity overlap: no repeated context" in bundle.instructions_text


def test_context_move_upload_batch_size_must_be_positive() -> None:
    try:
        ChunkOptions(upload_batch_size=0).validate()
    except ChunkingError as exc:
        assert "upload_batch_size must be positive" in str(exc)
    else:
        raise AssertionError("Expected an invalid upload batch size to fail validation")


def test_chunking_preserves_markdown_block_boundary_between_turns() -> None:
    document = RenderDocument(
        title="Markdown Boundaries",
        turns=[
            RenderTurn(
                role="user",
                turn_id="user-1",
                content="See the image.",
                media_items=[MediaItem(kind="asset_pointer", label="image.png", url="image.png")],
            ),
            RenderTurn(role="assistant", turn_id="assistant-1", content="I see it."),
        ],
    )

    bundle = build_markdown_chunks(document, stem="boundaries", options=ChunkOptions(overlap_turns=0))

    assert len(bundle.chunks) == 1
    assert "</details>\n\n### Assistant [Turn: assistant-1]" in bundle.chunks[0].text


def test_force_removes_only_stale_files_from_same_chunk_bundle(tmp_path) -> None:
    destination = tmp_path / "chunks"
    destination.mkdir()
    stale = destination / "conversation-part-001-of-009.md"
    unrelated = destination / "another-conversation-part-001-of-009.md"
    note = destination / "notes.md"
    stale.write_text("stale", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")
    note.write_text("keep", encoding="utf-8")
    bundle = build_markdown_chunks(_document("current"), stem="conversation")

    write_chunk_bundle(bundle, destination, force=True)

    assert not stale.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert note.read_text(encoding="utf-8") == "keep"
    assert (destination / bundle.manifest["chunks"][0]["filename"]).exists()
