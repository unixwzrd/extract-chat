"""Stable per-turn anchors and optional collapsed navigation."""

from hashlib import sha256
from html import escape
import re
from typing import Callable

from extract_chat.schemas.render_models import RenderTurn


def turn_anchor(identifier: str) -> str:
    return "turn-" + sha256(identifier.encode("utf-8")).hexdigest()[:16]


def turn_anchors(turn: RenderTurn) -> str:
    identifiers = turn.metadata.get("component_turn_ids") or [turn.turn_id]
    return "\n".join(f'<a id="{turn_anchor(identifier)}"></a>' for identifier in identifiers)


def render_turn_index(turns: list[RenderTurn], format_time: Callable, *, html: bool) -> str:
    lines = ['<details class="turn-index">', "<summary>Conversation index</summary>", ""]
    if html:
        lines.append('<table><thead><tr><th scope="col">Time</th><th scope="col">Role</th><th scope="col">Contents</th></tr></thead><tbody>')
    else:
        lines.extend(["| Time | Role | Contents |", "| --- | --- | --- |"])
    for turn in turns:
        full_stamp = format_time(turn.timestamp) if turn.timestamp is not None else "—"
        compact = re.sub(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.\d+)? ([^ ]+) \(UTC[^)]*\)$", r"\1 \2", full_stamp)
        stamp = escape(compact)
        plain = " ".join(turn.content.split()) or "Recorded activity"
        excerpt = plain
        if len(excerpt) > 80:
            cut = excerpt[:77]
            boundary = cut.rfind(" ")
            excerpt = (cut[:boundary] if boundary >= 38 else cut).rstrip() + "..."
        href = "#" + turn_anchor(turn.turn_id)
        if html:
            lines.append(f'<tr><td title="{escape(full_stamp, quote=True)}">{stamp}</td><td>{turn.role.title()}</td><td><a href="{href}" title="{escape(plain[:256], quote=True)}">{escape(excerpt)}</a></td></tr>')
        else:
            label = escape(excerpt).replace("|", "&#124;")
            lines.append(f'| {stamp} | {turn.role.title()} | <a href="{href}">{label}</a> |')
    if html:
        lines.append("</tbody></table>")
    lines.extend(["", "</details>"])
    return "\n".join(lines)
