"""Tests for the Conversation schema."""

from typing import Dict

from extract_chat.schemas.conversation import (
    Conversation,
    Message,
    MessageAuthor,
    MessageContent,
    Turn,
)


def test_conversation_async_status_accepts_int() -> None:
    """Ensure numeric async status values are coerced to strings."""

    conversation = Conversation(
        mapping={
            "root": Turn(
                id="root",
                message=Message(
                    author=MessageAuthor(role="user"),
                    content=MessageContent(text="Hello"),
                ),
            )
        },
        async_status=4,
    )

    assert conversation.async_status == "4"


def test_conversation_flow_handles_deep_chain() -> None:
    """Deep conversation trees should not exceed Python's recursion limit."""

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

    flow = conversation.get_conversation_flow_turns()

    assert len(flow) == depth
