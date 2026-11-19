"""Group one assistant exchange without merging independent branches."""

from extract_chat.context.document_context import DocumentContext
from extract_chat.schemas.render_models import RenderTurn, ToolActivityItem


def _descends_from(context: DocumentContext, child: str, ancestor: str) -> bool:
    seen: set[str] = set()
    current = child
    while current and current not in seen:
        seen.add(current)
        turn = context.get_turn(current)
        parent = getattr(turn, "parent", None)
        if parent == ancestor:
            return True
        if parent is None:
            return False
        if getattr(getattr(getattr(context.get_turn(parent), "message", None), "author", None), "role", None) == "user":
            return False
        current = parent
    return False


def group_assistant_updates(turns: list[RenderTurn], context: DocumentContext) -> list[RenderTurn]:
    grouped: list[RenderTurn] = []
    for turn in turns:
        previous = grouped[-1] if grouped else None
        exchange = turn.metadata.get("exchange_id")
        if previous is None or previous.role != "assistant" or turn.role != "assistant" or not exchange or exchange != previous.metadata.get("exchange_id") or previous.metadata.get("channel") != "commentary" or turn.metadata.get("channel") not in {"commentary", "final"} or previous.references_table or not _descends_from(context, turn.turn_id, previous.turn_id):
            grouped.append(turn)
            continue
        turn.metadata["component_turn_ids"] = previous.metadata.get("component_turn_ids", [previous.turn_id]) + [turn.turn_id]
        progress = ToolActivityItem(category="internal", title="Assistant commentary", content=previous.content, timestamp=previous.timestamp, turn_id=previous.turn_id, metadata={"presentation": "native", "role": "assistant", "author_name": previous.metadata.get("author_name"), "channel": previous.metadata.get("channel"), "status": previous.metadata.get("status"), "model_slug": previous.metadata.get("model_slug"), "context_citations": previous.metadata.get("context_citations", [])})
        turn.tools_used = sorted(previous.tools_used + [progress] + turn.tools_used, key=lambda item: (item.timestamp or 0, item.turn_id or ""))
        seen = set()
        media = []
        for item in previous.media_items + turn.media_items:
            key = (item.kind, item.url, item.label)
            if key not in seen:
                seen.add(key)
                media.append(item)
        turn.media_items = media
        grouped[-1] = turn
    return grouped
