"""Tests for the turn processor traversal logic."""

from typing import Dict

from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import (
    Conversation,
    Message,
    MessageAuthor,
    MessageContent,
    Turn,
)


def test_turn_processor_handles_deep_tree() -> None:
    """Processor should handle deeply nested conversations without recursion errors."""

    depth = 1200
    mapping: Dict[str, Turn] = {}

    for idx in range(depth):
        turn_id = f"turn-{idx}"
        mapping[turn_id] = Turn(
            id=turn_id,
            parent=f"turn-{idx - 1}" if idx else None,
            children=[f"turn-{idx + 1}"] if idx < depth - 1 else [],
            message=Message(
                author=MessageAuthor(role="assistant" if idx % 2 else "user"),
                content=MessageContent(text=f"Turn {idx}"),
            ),
        )

    conversation = Conversation(mapping=mapping)

    processor = TurnProcessorV2()

    blocks = processor.process_conversation(conversation)

    assert len(blocks) == depth


def test_assistant_visible_for_standard_models() -> None:
    """Assistant turns using normal chat models (e.g., gpt-5-1) stay visible."""

    mapping: Dict[str, Turn] = {
        "u1": Turn(
            id="u1",
            parent=None,
            children=["a1"],
            message=Message(
                author=MessageAuthor(role="user"),
                content=MessageContent(text="Hi"),
            ),
        ),
        "a1": Turn(
            id="a1",
            parent="u1",
            children=[],
            message=Message(
                author=MessageAuthor(role="assistant"),
                content=MessageContent(text="Hello back"),
                metadata={"model_slug": "gpt-5-1"},
            ),
        ),
    }

    conversation = Conversation(mapping=mapping)
    processor = TurnProcessorV2()

    blocks = processor.process_conversation(conversation)

    assert [b["type"] for b in blocks] == ["user", "assistant"]
