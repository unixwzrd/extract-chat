"""Interpret exported ChatGPT activity without guessing missing tool runs."""

from collections import defaultdict, deque
from typing import Any

from extract_chat.context.document_context import DocumentContext
from extract_chat.schemas.render_models import MediaItem, RenderTurn, ToolActivityItem


def reasoning_text(payload: dict[str, Any]) -> str:
    """Read exported summaries/content/chunks, never invent hidden reasoning."""
    parts: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            if value.strip() and value.strip() not in parts:
                parts.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            summary = value.get("summary")
            content = value.get("content") or value.get("text")
            if summary and (not isinstance(summary, str) or not isinstance(content, str) or summary.strip() != content.strip().strip("*")):
                collect(summary)
            collect(content)
            collect(value.get("chunks"))

    collect(payload.get("thoughts"))
    collect(payload.get("content"))
    return "\n\n".join(parts)


def context_citations(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for record in metadata.get("conversation_context_citation_metadata") or []:
        if not isinstance(record, dict) or not isinstance(record.get("citation"), dict):
            continue
        result.append({**record["citation"], "deleted": record.get("deleted", False)})
    return result


def image_generation_info(part: Any) -> dict[str, Any] | None:
    """Keep a returned image's generation provenance attached to its asset."""
    if not isinstance(part, dict) or not part.get("asset_pointer"):
        return None
    metadata = part.get("metadata")
    if not isinstance(metadata, dict):
        return None
    dalle = metadata.get("dalle") if isinstance(metadata.get("dalle"), dict) else {}
    generation = metadata.get("generation") if isinstance(metadata.get("generation"), dict) else {}
    if not dalle and not generation:
        return None
    info = {"asset_pointer": part["asset_pointer"]}
    prompt = dalle.get("prompt")
    if isinstance(prompt, str) and prompt:
        info.update(prompt=prompt, prompt_source="returned image metadata.dalle.prompt")
    for key in ("width", "height", "size_bytes"):
        value = part.get(key) if part.get(key) is not None else generation.get(key)
        if value is not None:
            info[key] = value
    parameters = {key: value for key, value in generation.items() if value is not None}
    parameters.update({key: value for key, value in dalle.items() if key != "prompt" and value is not None})
    if parameters:
        info["parameters"] = parameters
    return info


def image_generation_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        image = image_generation_info(value)
        if image:
            return [image]
        return [image for child in value.values() for image in image_generation_records(child)]
    if isinstance(value, list):
        return [image for child in value for image in image_generation_records(child)]
    return []


def native_activity_metadata(message: Any) -> dict[str, Any]:
    metadata = getattr(message, "metadata", None) or {}
    author = getattr(message, "author", None)
    content = getattr(message, "content", None)
    return {
        "presentation": "native",
        "role": getattr(author, "role", None),
        "author_name": getattr(author, "name", None),
        "model_slug": metadata.get("model_slug") or getattr(message, "model_slug", None),
        "recipient": getattr(message, "recipient", None),
        "tool_name": getattr(author, "name", None) if getattr(author, "role", None) == "tool" else getattr(message, "recipient", None),
        "request_id": metadata.get("tool_call_id") or getattr(message, "tool_call_id", None),
        "parent_id": metadata.get("parent_id"),
        "channel": getattr(message, "channel", None),
        "status": getattr(message, "status", None),
        "native_content": content.model_dump(exclude_none=True) if hasattr(content, "model_dump") else {},
        "images": image_generation_records(content.model_dump(exclude_none=True)) if hasattr(content, "model_dump") else [],
        "exported_details": {
            key: value for key, value in metadata.items()
            if value is not None and key in {
                "thinking_effort", "reasoning_status", "reasoning_start_time", "reasoning_end_time",
                "reasoning_title", "reasoning_titles", "tool_icons", "tool_summary_type",
                "work_activity", "aggregate_result", "image_gen_title", "command",
                "async_task_id", "async_task_conversation_id", "is_async_task_result_message",
                "request_id", "turn_id", "turn_exchange_id", "working_turn_id",
                "search_queries", "search_result_groups",
                "files", "file_changes", "changes", "patch", "patches", "diff",
            }
        },
        "context_citations": context_citations(metadata),
    }


def attach_native_activity(
    turns: list[RenderTurn],
    activities: list[tuple[ToolActivityItem, list[MediaItem]]],
    context: DocumentContext,
) -> list[RenderTurn]:
    """Attach by parent ancestry, not just the next timestamp/user boundary."""
    visible = {turn.turn_id: turn for turn in turns if turn.role == "assistant"}
    children: dict[str, list[str]] = defaultdict(list)
    mapping = getattr(context.conversation, "mapping", {})
    for uid, node in mapping.items():
        if node.parent:
            children[node.parent].append(uid)
    for activity, media in activities:
        # Prefer the first visible answer/update on this descendant path.
        queue = deque(children.get(activity.turn_id, []))
        visited = set()
        target = None
        while queue:
            uid = queue.popleft()
            if uid in visited:
                continue
            visited.add(uid)
            node = context.get_turn(uid)
            role = getattr(getattr(getattr(node, "message", None), "author", None), "role", None)
            if role == "user":
                continue
            if uid in visible:
                # Multiple visible descendant branches are ambiguous; don't
                # assign one branch's activity to a timestamp-adjacent sibling.
                candidate = visible[uid]
                if target is not None and target is not candidate:
                    target = None
                    break
                target = candidate
                continue
            queue.extend(children.get(uid, []))
        if target is None:
            node = context.get_turn(activity.turn_id)
            uid = getattr(node, "parent", None)
            visited = set()
            while uid and uid not in visited:
                visited.add(uid)
                node = context.get_turn(uid)
                if getattr(getattr(getattr(node, "message", None), "author", None), "role", None) == "user":
                    break
                if uid in visible:
                    target = visible[uid]
                    break
                uid = getattr(node, "parent", None)
        if target is None:
            target = RenderTurn(role="assistant", turn_id=activity.turn_id, timestamp=activity.timestamp, metadata={"activity_only": True, "model_slug": activity.metadata.get("model_slug")})
            turns.append(target)
        target.tools_used.append(activity)
        target.media_items.extend(media)
    return [turn for _, turn in sorted(enumerate(turns), key=lambda pair: (pair[1].timestamp if pair[1].timestamp is not None else float("inf"), pair[0]))]


def pair_native_tools(tools: list[ToolActivityItem], context: DocumentContext) -> None:
    """Pair explicit call IDs or matching tool ancestors; never timestamp-only."""
    calls = {item.turn_id: item for item in tools if item.category == "tool_call" and item.metadata.get("presentation") == "native"}
    for item in tools:
        if item.category != "tool_output" or item.metadata.get("presentation") != "native":
            continue
        direct_parent = getattr(context.get_turn(item.turn_id), "parent", None)
        uid = direct_parent
        visited = set()
        while uid and uid not in visited:
            visited.add(uid)
            node = context.get_turn(uid)
            if getattr(getattr(getattr(node, "message", None), "author", None), "role", None) == "user":
                break
            call = calls.get(uid)
            if call:
                call_id, output_id = call.metadata.get("request_id"), item.metadata.get("request_id")
                exact_id = call_id and output_id and call_id == output_id
                same_tool = call.metadata.get("tool_name") == item.metadata.get("tool_name") and call.metadata.get("tool_name") not in {None, "", "all"}
                namespace = str(item.metadata.get("tool_name") or "")
                direct_namespace = uid == direct_parent and bool(namespace) and str(call.metadata.get("tool_name") or "").startswith(namespace + ".")
                if exact_id or (not (call_id and output_id) and (same_tool or direct_namespace)):
                    call.metadata["pair_id"] = item.metadata["pair_id"] = uid
                    item.metadata["pairing"] = "call ID and parent ancestry" if exact_id else "direct parent and tool namespace" if direct_namespace else "tool name and parent ancestry"
                    break
            uid = getattr(node, "parent", None)
