"""Collapsed, inert thoughts and paired tool payloads for agent exports."""

from html import escape
from collections.abc import Callable
import json
import re
from typing import Any
from urllib.parse import urlsplit

from extract_chat.schemas.render_models import ToolActivityItem

JSON_DISPLAY_LABELS = {
    "readable": "Readable JSON (decoded strings) + Raw JSON",
    "pretty": "Formatted JSON (escaped)",
    "raw": "Original JSON (escaped)",
}


def _code_block(text: str, *, html: bool, language: str = "text") -> str:
    if html:
        return f'<pre><code class="language-{escape(language)}">{escape(text)}</code></pre>'
    runs = re.findall(r"`+", text)
    fence = "`" * max(3, 1 + max(map(len, runs), default=0))
    return "\n".join([fence + language, text, fence])


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key; retain the raw view instead.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Nonstandard JSON constant: {value}")


def _numbered_lines(text: str) -> str:
    """Space a consecutive numbered-file gutter, not arbitrary pipe text."""
    lines = text.split("\n")
    trailing_newline = lines[-1] == ""
    if trailing_newline:
        lines = lines[:-1]
    matches = [re.fullmatch(r"[ \t]*(\d+)\|(.*)", line) for line in lines]
    if len(matches) < 2 or not all(matches):
        return text
    numbers = [int(match[1]) for match in matches]
    if any(right != left + 1 for left, right in zip(numbers, numbers[1:])):
        return text
    width = max(len(match[1]) for match in matches)
    return "\n".join(f"{match[1].rjust(width)} | {match[2]}" for match in matches) + ("\n" if trailing_newline else "")


def _readable_json(value: Any) -> str:
    """JSON-shaped human display; decoded strings need not be valid JSON."""
    leaves = 0

    def render(item: Any, depth: int = 0, column: int = 0) -> str:
        nonlocal leaves
        if depth > 32 or leaves >= 256:
            raise ValueError("Payload is too deeply structured for a readable view.")
        if isinstance(item, dict) and item:
            lines = []
            for key, child in item.items():
                prefix = "  " * (depth + 1) + json.dumps(key, ensure_ascii=False) + ": "
                lines.append(prefix + render(child, depth + 1, len(prefix)))
            return "{\n" + ",\n".join(lines) + "\n" + "  " * depth + "}"
        if isinstance(item, list) and item:
            prefix = "  " * (depth + 1)
            lines = [prefix + render(child, depth + 1, len(prefix)) for child in item]
            return "[\n" + ",\n".join(lines) + "\n" + "  " * depth + "]"
        leaves += 1
        if isinstance(item, str):
            # Only json.loads decodes escapes. Retain literal backslashes and
            # existing content indentation, adding display-only alignment.
            return '"' + ("\n" + " " * (column + 1)).join(_numbered_lines(item).split("\n")) + '"'
        return json.dumps(item, ensure_ascii=False)

    return render(value)


def render_json_payload(content: str, *, html: bool, mode: str = "readable") -> str | None:
    """Decode one JSON layer for display, retaining the untouched raw payload.

    Do not apply unicode_escape or global backslash replacements to command
    strings. A literal \\n after JSON decoding must stay literal, not become LF.
    """
    if mode not in {"readable", "pretty", "raw"}:
        raise ValueError("Tool JSON display must be readable, pretty, or raw.")
    if not content.lstrip().startswith(("{", "[")):
        return None
    try:
        value = json.loads(content, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        if mode in {"raw", "pretty"}:
            text = content if mode == "raw" else json.dumps(value, ensure_ascii=False, indent=2)
            return _code_block(text, html=html, language="json")
        readable = _readable_json(value)
    except (ValueError, RecursionError):
        return None
    rendered = [_code_block(readable, html=html)]
    rendered.extend(["<details>", "<summary>Raw JSON</summary>", "", _code_block(content, html=html, language="json"), "", "</details>"])
    return "\n\n".join(rendered)


def _disclosure(title: str, body: str, *, css: str = "", html: bool) -> str:
    attribute = f' class="{css}"' if css else ""
    return f'<details{attribute}><summary>{escape(title)}</summary>\n\n{body}\n\n</details>'


def _unescape_heredoc_quotes(content: str) -> str:
    """Remove one double-quote escape layer in JSON heredocs, in place."""
    pattern = r"<<[ \t]*(['\"])JSON\1[ \t]*\n(.*?)\nJSON(?:[\"'])?[ \t]*(?=\n|$)"

    def replace(match: re.Match[str]) -> str:
        try:
            json.loads(match[2], object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            return match[0]  # Already valid: retain required JSON escapes.
        except (ValueError, RecursionError):
            pass
        body = re.sub(r'(\\+)"', lambda quote: "\\" * (len(quote[1]) // 2) + '"' if len(quote[1]) % 2 else quote[0], match[2])
        try:
            value = json.loads(body, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            return match[0]
        if not isinstance(value, (dict, list)):
            return match[0]
        start, end = match.start(2) - match.start(), match.end(2) - match.start()
        return match[0][:start] + body + match[0][end:]

    return re.sub(pattern, replace, content, flags=re.DOTALL)


def render_context_citations(citations: list[dict[str, Any]], *, html: bool) -> str:
    """Memory attribution is context provenance, not an attachment/tool run."""
    if not citations:
        return ""
    rendered = []
    for citation in citations:
        title = str(citation.get("title") or citation.get("conversation_title") or "Exported context")
        kind = str(citation.get("attribution") or citation.get("conversation_context_type") or "Context")
        url = str(citation.get("url") or "")
        is_memory = citation.get("conversation_context_type") == "general_memory" or kind.casefold() == "memory" or url.startswith("#settings/")
        if is_memory:
            url = ""
        elif url.startswith("/c/"):
            url = "https://chatgpt.com/" + url.lstrip("/")
        try:
            parsed = urlsplit(url)
        except ValueError:
            parsed = urlsplit("")
        label = escape(title)
        if parsed.scheme in {"http", "https"} and parsed.netloc and not any(ord(char) < 32 for char in url):
            label = f'<a href="{escape(url, quote=True)}">{label}</a>'
        lines = [f'<p><strong>{escape(kind)}: {label}</strong></p>']
        if citation.get("deleted"):
            lines.append("<p>Marked deleted in the exported citation record.</p>")
        for key, caption in (("snippet", "Excerpt"), ("reason", "Reason")):
            value = citation.get(key)
            if value and str(value) != title:
                lines.append(f'<p><strong>{caption}:</strong> {escape(str(value)).replace(chr(10), "<br>")}</p>')
        rendered.append("\n".join(lines))
    noun = "citation" if len(citations) == 1 else "citations"
    return _disclosure(f"Context used ({len(citations)} {noun})", "\n\n".join(rendered), css="context-citations", html=html)


def _activity_metadata(item: ToolActivityItem, *, html: bool, format_time: Callable | None) -> str:
    """Label identity/time separately instead of joining an opaque status line."""
    fields: list[tuple[str, str]] = []
    role = item.metadata.get("role")
    if not role:
        role = "tool" if item.category == "tool_output" else "assistant"
    author = str(role).title()
    name = item.metadata.get("author_name")
    if name:
        author += f": {name}"
    fields.append(("Author", author))
    if item.timestamp is not None:
        fields.append(("Time", format_time(item.timestamp) if format_time else str(item.timestamp)))
    for key, caption in (("model_slug", "Model"), ("tool_name", "Tool"), ("channel", "Channel"), ("status", "Message status")):
        if item.metadata.get(key) not in {None, "", "all"}:
            fields.append((caption, str(item.metadata[key])))
    if item.turn_id:
        fields.append(("Turn ID", item.turn_id))
    if html:
        rows = []
        for key, value in fields:
            display = f"<code>{escape(value)}</code>" if key == "Turn ID" else escape(value)
            rows.append(f"<dt>{key}</dt><dd>{display}</dd>")
        return '<dl class="activity-metadata">' + "".join(rows) + "</dl>"
    rows = ["| Field | Value |", "| --- | --- |"]
    rows.extend(f'| {key} | {escape(value).replace(chr(124), "&#124;").replace(chr(10), "<br>")} |' for key, value in fields)
    return "\n".join(rows)


def render_image_generation(info: dict[str, Any], *, html: bool) -> str:
    """Show exported image prompts as inert text, not opaque nested JSON."""
    parts = []
    if info.get("local_path"):
        label = info.get("display_name") or "captured image"
        parts.append(f'<p><a href="{escape(str(info["local_path"]), quote=True)}">View image: {escape(str(label))}</a></p>')
    if info.get("width") is not None and info.get("height") is not None:
        parts.append(f'<p><strong>Image dimensions:</strong> {escape(str(info["width"]))} × {escape(str(info["height"]))} pixels</p>')
    if info.get("prompt"):
        parts.append('<p><strong>Image-generation prompt</strong></p>')
        parts.append(f'<p class="export-limitation">Source: {escape(str(info.get("prompt_source") or "exported image metadata"))}</p>')
        parts.append(_code_block(str(info["prompt"]), html=html))
    if info.get("parameters"):
        parts.append(_disclosure("Generation parameters", _code_block(json.dumps(info["parameters"], indent=2, ensure_ascii=False), html=html, language="json"), html=html))
    return "\n\n".join(parts)


def _render_native_activity(tools: list[ToolActivityItem], *, html: bool, json_mode: str, format_time: Callable | None, render_text: Callable | None) -> str:
    groups: dict[str, list[ToolActivityItem]] = {}
    for index, item in enumerate(tools):
        key = item.metadata.get("pair_id") or f"record-{index}"
        groups.setdefault(key, []).append(item)
    rendered = []
    for items in groups.values():
        call = next((item for item in items if item.category == "tool_call"), None)
        title = call.title if call else items[0].title
        if call:
            result_count = sum(item.category == "tool_output" for item in items)
            title += f" — {result_count} result" + ("s" if result_count != 1 else "") + " recorded" if result_count else " — no matching result"
        if not call and items[0].category == "tool_output":
            title = "Tool result: " + str(items[0].metadata.get("tool_name") or items[0].metadata.get("recipient") or "Unknown tool")
        if items[0].category == "reasoning" and items[0].content.strip():
            title += " — " + " ".join(items[0].content.split("\n", 1)[0].replace("**", "").split())[:100]
        parts = []
        for item in items:
            label = "Arguments / command" if item.category == "tool_call" else "Result / output" if item.category == "tool_output" else item.title
            if item.category in {"tool_call", "tool_output"}:
                parts.append(f"<p><strong>{escape(label)}</strong></p>" if html else f"**{escape(label)}**\n")
            parts.append(_activity_metadata(item, html=html, format_time=format_time))
            exported = dict(item.metadata.get("exported_details") or {})
            raw_content = item.metadata.get("native_content") or {}
            for key in ("files", "file_changes", "changes", "patch", "patches", "diff"):
                if raw_content.get(key) is not None:
                    exported.setdefault(key, raw_content[key])
            activity_title = exported.get("reasoning_title")
            if activity_title:
                parts.append(f'<p><strong>Reported activity:</strong> {escape(str(activity_title))}</p>')
            work = exported.get("work_activity") or {}
            if isinstance(work, dict):
                for group in work.get("groups", []):
                    for record in group.get("items", []) if isinstance(group, dict) else []:
                        if not isinstance(record, dict):
                            continue
                        kind = {"file-change": "file change" if record.get("count") == 1 else "file changes", "command": "command" if record.get("count") == 1 else "commands"}.get(record.get("kind"), record.get("kind") or "activity")
                        parts.append(f'<p><strong>Recorded work:</strong> {escape(str(record.get("count", "")))} {escape(str(kind))} · {escape(str(record.get("status") or "status not exported"))}</p>')
                        if record.get("kind") == "file-change" and not any(record.get(key) for key in ("files", "file_path", "path", "filename", "changes", "patch", "diff")):
                            parts.append('<p class="export-limitation">This work summary contains a count only, not a file list or individual change types.</p>')
            if exported.get("image_gen_title"):
                parts.append(f'<p><strong>Image:</strong> {escape(str(exported["image_gen_title"]))}</p>')
            for key in ("patch", "patches", "diff", "files", "file_changes", "changes"):
                value = exported.get(key)
                if value:
                    caption = "Patch / diff" if key in {"patch", "patches", "diff"} else "Exported file details"
                    parts.append(f'<p><strong>{caption}</strong></p>')
                    parts.append(_code_block(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False), html=html, language="diff" if isinstance(value, str) else "json"))
            if item.content.strip():
                is_reasoning = item.category == "reasoning"
                payload = None if is_reasoning else render_json_payload(item.content, html=html, mode=json_mode)
                if payload is not None:
                    parts.append(payload)
                elif item.category in {"tool_call", "tool_output", "hidden_assistant"}:
                    content = _unescape_heredoc_quotes(item.content) if item.category == "tool_call" and json_mode == "readable" else item.content
                    parts.append(_code_block(content, html=html, language=item.language or "text"))
                elif html:
                    parts.append(render_text(item.content) if render_text else "<p>" + escape(item.content).replace("\n", "<br>") + "</p>")
                else:
                    parts.append(escape(item.content, quote=False))
                if item.category == "tool_call" and item.content.strip().endswith(" apply_patch") and not any(exported.get(key) for key in ("patch", "patches", "diff", "changes")):
                    parts.append('<p class="export-limitation">No patch body was included in the exported command or its patch fields.</p>')
            elif item.category == "reasoning":
                parts.append("<p>No reasoning text was included in the export.</p>")
            elif item.category == "tool_output" and not item.metadata.get("images"):
                parts.append("<p>No text output was exported. Any captured media is shown with the answer.</p>")
            for image in item.metadata.get("images") or []:
                parts.append(render_image_generation(image, html=html))
            if item.category == "tool_call" and not any(other.category == "tool_output" for other in items):
                parts.append("<p>No matching result is recorded in this activity group.</p>")
            if item.category == "tool_output" and call is None:
                parts.append("<p>No matching call could be established from the exported links.</p>")
            details = dict(exported)
            aggregate = details.get("aggregate_result")
            if isinstance(aggregate, dict) and aggregate.get("final_expression_output") == item.content:
                details["aggregate_result"] = {key: value for key, value in aggregate.items() if key != "final_expression_output"}
            if item.metadata.get("pairing"):
                details["paired_by"] = item.metadata["pairing"]
            queries = item.metadata.get("search_queries")
            if queries:
                details.setdefault("search_queries", queries)
                labels = [str(query.get("q") or "") if isinstance(query, dict) else str(query) for query in queries]
                parts.append("<p><strong>Search Queries</strong></p><ul>" + "".join(f"<li>{escape(label)}</li>" for label in labels if label) + "</ul>")
            raw_content = item.metadata.get("native_content")
            if raw_content and (not item.content or item.category == "reasoning"):
                details["exported_content"] = raw_content
            if details:
                parts.append(_disclosure("Exported fields", _code_block(json.dumps(details, ensure_ascii=False, indent=2), html=html, language="json"), html=html))
            citations = item.metadata.get("context_citations")
            if citations:
                parts.append(render_context_citations(citations, html=html))
        rendered.append(_disclosure(title, "\n\n".join(parts), css="agent-activity", html=html))
    calls = sum(item.category == "tool_call" for item in tools)
    summary = f"Activity ({len(tools)} records" + (f", {calls} tool calls)" if calls else ")")
    return _disclosure(summary, "\n\n".join(rendered), css="tools-used", html=html)


def render_activity_details(tools: list[ToolActivityItem], *, html: bool, json_mode: str = "readable", format_time: Callable | None = None, render_text: Callable | None = None) -> str:
    """Render source-aware activity without interpreting tool payloads as HTML."""
    if not any(item.metadata.get("source") == "hermes" for item in tools):
        return _render_native_activity(tools, html=html, json_mode=json_mode, format_time=format_time, render_text=render_text)
    groups: list[tuple[str, list[ToolActivityItem]]] = []
    requests: dict[str, list[ToolActivityItem]] = {}
    for item in tools:
        if item.category == "reasoning":
            if item.content.strip():
                groups.append(("Thought", [item]))
            continue
        request_id = item.metadata.get("request_id")
        if request_id and item.category in {"tool_call", "tool_output"}:
            if request_id not in requests:
                requests[request_id] = []
                name = item.metadata.get("recipient") or "Unknown tool"
                groups.append((f"Tool call: {name}", requests[request_id]))
            requests[request_id].append(item)
        else:
            groups.append((item.title, [item]))
    rendered = []
    for title, items in groups:
        if any(item.category == "tool_output" for item in items) and not any(item.category == "tool_call" for item in items):
            title = title.replace("Tool call:", "Tool result:", 1)
        if html:
            parts = [f'<details class="agent-activity"><summary>{escape(title)}</summary>']
            for item in items:
                label = "Arguments" if item.category == "tool_call" else "Result" if item.category == "tool_output" else "Thought"
                payload = render_json_payload(item.content, html=True, mode=json_mode) if item.category in {"tool_call", "tool_output"} else None
                parts.extend([f"<p><strong>{label}</strong></p>", payload if payload is not None else _code_block(item.content, html=True)])
            parts.append("</details>")
        else:
            parts = ["<details>", f"<summary>{escape(title)}</summary>", ""]
            for item in items:
                label = "Arguments" if item.category == "tool_call" else "Result" if item.category == "tool_output" else "Thought"
                payload = render_json_payload(item.content, html=False, mode=json_mode) if item.category in {"tool_call", "tool_output"} else None
                parts.extend([f"**{label}**", "", payload if payload is not None else _code_block(item.content, html=False), ""])
            parts.append("</details>")
        rendered.append("\n".join(parts))
    return "\n\n".join(rendered)
