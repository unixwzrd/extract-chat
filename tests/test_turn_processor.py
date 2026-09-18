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


def test_turn_processor_orders_branches_by_message_timestamp() -> None:
    """Sibling branches must appear when they occurred, not in tree preorder."""

    mapping: Dict[str, Turn] = {
        "root": Turn(id="root", parent=None, children=["new-user"]),
        "new-user": Turn(
            id="new-user",
            parent="root",
            children=["new-assistant"],
            message=Message(
                create_time=30,
                author=MessageAuthor(role="user"),
                content=MessageContent(text="New question"),
            ),
        ),
        "new-assistant": Turn(
            id="new-assistant",
            parent="new-user",
            children=[],
            message=Message(
                create_time=40,
                author=MessageAuthor(role="assistant"),
                content=MessageContent(text="New answer"),
            ),
        ),
        "old-user": Turn(
            id="old-user",
            parent="missing-export-node",
            children=["old-assistant"],
            message=Message(
                create_time=10,
                author=MessageAuthor(role="user"),
                content=MessageContent(text="Old question"),
            ),
        ),
        "old-assistant": Turn(
            id="old-assistant",
            parent="old-user",
            children=[],
            message=Message(
                create_time=20,
                author=MessageAuthor(role="assistant"),
                content=MessageContent(text="Old answer"),
            ),
        ),
    }

    document = TurnProcessorV2().process_conversation(Conversation(mapping=mapping))

    assert [turn.turn_id for turn in document.turns] == ["old-user", "old-assistant", "new-user", "new-assistant"]
    assert [turn.timestamp for turn in document.turns] == [10, 20, 30, 40]
