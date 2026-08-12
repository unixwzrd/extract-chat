"""Deterministic Markdown continuity chunks with a mandatory 512 KiB ceiling."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.schemas.render_models import RenderDocument, RenderTurn

MAX_CHUNK_BYTES = 512 * 1024
ChunkStrategy = Literal["hybrid", "turn", "heading", "paragraph", "fixed"]


class ChunkingError(RuntimeError):
    """Raised when requested chunk constraints cannot be satisfied."""


@dataclass(frozen=True)
class ChunkOptions:
    strategy: ChunkStrategy = "hybrid"
    max_bytes: int = MAX_CHUNK_BYTES
    max_lines: int | None = None
    max_tokens: int | None = None
    token_encoding: str = "o200k_base"
    overlap_turns: int = 1
    overlap_lines: int = 0
    overlap_bytes: int = 0

    def validate(self) -> None:
        if not 1 <= self.max_bytes <= MAX_CHUNK_BYTES:
            raise ChunkingError(f"max_bytes must be between 1 and {MAX_CHUNK_BYTES}")
        for label, value in (("max_lines", self.max_lines), ("max_tokens", self.max_tokens)):
            if value is not None and value <= 0:
                raise ChunkingError(f"{label} must be positive")
        overlaps = sum(bool(value) for value in (self.overlap_turns, self.overlap_lines, self.overlap_bytes))
        if overlaps > 1:
            raise ChunkingError("Choose only one overlap mode: turns, lines, or bytes")
        if min(self.overlap_turns, self.overlap_lines, self.overlap_bytes) < 0:
            raise ChunkingError("Overlap values cannot be negative")


@dataclass
class ChunkBlock:
    text: str
    turn_ids: list[str]
    source_index: int
    fragment_index: int = 0


@dataclass
class MarkdownChunk:
    text: str
    turn_ids: list[str]
    overlap_turn_ids: list[str] = field(default_factory=list)
    fragment_ids: list[str] = field(default_factory=list)
    byte_count: int = 0
    line_count: int = 0
    token_count: int | None = None
    sha256: str = ""


@dataclass
class ChunkBundle:
    chunks: list[MarkdownChunk]
    index_text: str
    manifest: dict


def _token_counter(encoding_name: str) -> Callable[[str], int]:
    try:
        import tiktoken  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ChunkingError(
            "Token limits require the optional 'tiktoken' dependency. "
            "Install extract-chat[token-counting] or omit --chunk-max-tokens."
        ) from exc
    encoding = tiktoken.get_encoding(encoding_name)
    return lambda text: len(encoding.encode(text))


def _measure(text: str, options: ChunkOptions, token_count: Callable[[str], int] | None) -> tuple[int, int, int | None]:
    return len(text.encode("utf-8")), len(text.splitlines()), token_count(text) if token_count else None


def _fits(text: str, options: ChunkOptions, token_count: Callable[[str], int] | None) -> bool:
    byte_count, line_count, tokens = _measure(text, options, token_count)
    return (
        byte_count <= options.max_bytes
        and (options.max_lines is None or line_count <= options.max_lines)
        and (options.max_tokens is None or (tokens is not None and tokens <= options.max_tokens))
    )


def _largest_utf8_prefix(text: str, byte_limit: int) -> tuple[str, str]:
    raw = text.encode("utf-8")
    if len(raw) <= byte_limit:
        return text, ""
    cut = max(1, byte_limit)
    while cut > 0:
        try:
            prefix = raw[:cut].decode("utf-8")
            return prefix, raw[cut:].decode("utf-8")
        except UnicodeDecodeError:
            cut -= 1
    raise ChunkingError("Unable to split UTF-8 content")


def _preferred_boundaries(text: str, strategy: ChunkStrategy) -> list[int]:
    patterns: list[str] = []
    if strategy in {"hybrid", "heading"}:
        patterns.append(r"(?m)(?=^#{1,6}\s)")
    if strategy in {"hybrid", "heading", "paragraph"}:
        patterns.append(r"\n\n+")
    patterns.append(r"\n")
    boundaries: set[int] = set()
    for pattern in patterns:
        boundaries.update(match.start() for match in re.finditer(pattern, text))
        boundaries.update(match.end() for match in re.finditer(pattern, text))
    return sorted(boundary for boundary in boundaries if 0 < boundary < len(text))


def _split_oversized_text(
    text: str,
    options: ChunkOptions,
    token_count: Callable[[str], int] | None,
) -> list[str]:
    if _fits(text, options, token_count):
        return [text]
    if options.strategy == "turn":
        raise ChunkingError("A single turn exceeds the selected limits with --chunk-strategy turn")

    pieces: list[str] = []
    remaining = text
    while remaining:
        if _fits(remaining, options, token_count):
            pieces.append(remaining)
            break
        candidates = _preferred_boundaries(remaining, options.strategy)
        chosen = ""
        for boundary in reversed(candidates):
            candidate = remaining[:boundary].rstrip() + "\n"
            if candidate.strip() and _fits(candidate, options, token_count):
                chosen = candidate
                remaining = remaining[boundary:].lstrip("\n")
                break
        if chosen:
            pieces.append(chosen)
            continue

        byte_limit = min(options.max_bytes, len(remaining.encode("utf-8")) - 1)
        prefix, suffix = _largest_utf8_prefix(remaining, byte_limit)
        while prefix and not _fits(prefix, options, token_count):
            prefix, returned = _largest_utf8_prefix(prefix, max(1, len(prefix.encode("utf-8")) - 1))
            suffix = returned + suffix
        if not prefix:
            raise ChunkingError("The selected line/token limits cannot fit any content")
        pieces.append(prefix)
        remaining = suffix
    return pieces


def _header(document: RenderDocument, part: int, total: int, previous_name: str | None, next_name: str | None) -> str:
    lines = [
        f"# {document.title or 'Chat Conversation'} — Continuity Part {part} of {total}",
        "",
        f"**Conversation ID:** {document.conversation_id or 'unknown'}",
        f"**Part:** {part} of {total}",
    ]
    if previous_name:
        lines.append(f"**Previous:** `{previous_name}`")
    if next_name:
        lines.append(f"**Next:** `{next_name}`")
    lines.extend(
        [
            "",
            "> This is an ordered continuation of an earlier ChatGPT conversation. "
            "Use the overlapped context only for continuity and continue from the new content.",
            "",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def _render_turn(formatter: MarkdownFormatter, turn: RenderTurn) -> str:
    return formatter.render_turn(turn).rstrip() + "\n"


def build_markdown_chunks(
    document: RenderDocument,
    *,
    stem: str,
    options: ChunkOptions | None = None,
) -> ChunkBundle:
    """Build deterministic chunks and validate every final file against all budgets."""

    options = options or ChunkOptions()
    options.validate()
    token_count = _token_counter(options.token_encoding) if options.max_tokens else None
    formatter = MarkdownFormatter()

    # Reserve enough space for final navigation headers before splitting turn bodies.
    reserve = _header(document, 999999, 999999, f"{stem}-part-999999-of-999999.md", f"{stem}-part-999999-of-999999.md")
    body_options = ChunkOptions(
        strategy=options.strategy,
        max_bytes=max(1, options.max_bytes - len(reserve.encode("utf-8")) - 128),
        max_lines=max(1, options.max_lines - len(reserve.splitlines()) - 2) if options.max_lines else None,
        max_tokens=max(1, options.max_tokens - token_count(reserve) - 16) if options.max_tokens and token_count else None,
        token_encoding=options.token_encoding,
        overlap_turns=0,
    )

    blocks: list[ChunkBlock] = []
    for source_index, turn in enumerate(document.turns):
        rendered = _render_turn(formatter, turn)
        fragments = _split_oversized_text(rendered, body_options, token_count)
        blocks.extend(
            ChunkBlock(text=fragment, turn_ids=[turn.turn_id], source_index=source_index, fragment_index=index)
            for index, fragment in enumerate(fragments)
        )

    groups: list[list[ChunkBlock]] = []
    current: list[ChunkBlock] = []
    for block in blocks:
        candidate = "\n".join(item.text.rstrip() for item in [*current, block]).rstrip() + "\n"
        if current and not _fits(candidate, body_options, token_count):
            groups.append(current)
            current = [block]
        else:
            current.append(block)
    if current:
        groups.append(current)

    total = len(groups)
    filenames = [f"{stem}-part-{index:03d}-of-{total:03d}.md" for index in range(1, total + 1)]
    chunks: list[MarkdownChunk] = []
    previous_source_blocks: list[ChunkBlock] = []
    for index, group in enumerate(groups):
        overlap: list[ChunkBlock] = []
        overlap_text = ""
        if index > 0 and options.overlap_turns:
            distinct_turns: list[str] = []
            for block in reversed(previous_source_blocks):
                turn_id = block.turn_ids[0]
                if turn_id not in distinct_turns:
                    distinct_turns.append(turn_id)
                if len(distinct_turns) > options.overlap_turns:
                    break
                overlap.insert(0, block)

        if index > 0 and options.overlap_lines:
            prior = "\n".join(block.text.rstrip() for block in previous_source_blocks).rstrip()
            overlap_text = "\n".join(prior.splitlines()[-options.overlap_lines :])
        elif index > 0 and options.overlap_bytes:
            prior = "\n".join(block.text.rstrip() for block in previous_source_blocks).rstrip()
            raw = prior.encode("utf-8")[-options.overlap_bytes :]
            while raw:
                try:
                    overlap_text = raw.decode("utf-8")
                    break
                except UnicodeDecodeError:
                    raw = raw[1:]

        header = _header(
            document,
            index + 1,
            total,
            filenames[index - 1] if index else None,
            filenames[index + 1] if index + 1 < total else None,
        )
        new_body = "\n".join(block.text.rstrip() for block in group).rstrip() + "\n"
        overlap_body = overlap_text or "\n".join(block.text.rstrip() for block in overlap).rstrip()
        if overlap_body:
            candidate = f"{header}## Overlapped Context\n\n{overlap_body}\n\n---\n\n## New Content\n\n{new_body}"
            if not _fits(candidate, options, token_count):
                overlap = []
                overlap_text = ""
        if overlap or overlap_text:
            overlap_body = overlap_text or "\n".join(block.text.rstrip() for block in overlap).rstrip()
            text = f"{header}## Overlapped Context\n\n{overlap_body}\n\n---\n\n## New Content\n\n{new_body}"
        else:
            text = f"{header}## New Content\n\n{new_body}"
        if not text.endswith("\n"):
            text += "\n"
        if not _fits(text, options, token_count):
            raise ChunkingError(f"Final chunk {index + 1} exceeds the selected limits")
        byte_count, line_count, tokens = _measure(text, options, token_count)
        chunks.append(
            MarkdownChunk(
                text=text,
                turn_ids=list(dict.fromkeys(turn_id for block in group for turn_id in block.turn_ids)),
                overlap_turn_ids=list(dict.fromkeys(turn_id for block in overlap for turn_id in block.turn_ids)),
                fragment_ids=[f"{block.turn_ids[0]}:{block.fragment_index}" for block in group],
                byte_count=byte_count,
                line_count=line_count,
                token_count=tokens,
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
        previous_source_blocks.extend(group)

    manifest = {
        "format_version": 1,
        "source_conversation_id": document.conversation_id,
        "stem": stem,
        "strategy": options.strategy,
        "limits": {
            "max_bytes": options.max_bytes,
            "absolute_max_bytes": MAX_CHUNK_BYTES,
            "max_lines": options.max_lines,
            "max_tokens": options.max_tokens,
            "token_encoding": options.token_encoding if options.max_tokens else None,
        },
        "overlap": {
            "turns": options.overlap_turns,
            "lines": options.overlap_lines,
            "bytes": options.overlap_bytes,
        },
        "chunk_count": len(chunks),
        "chunks": [
            {
                "filename": filenames[index],
                "byte_count": chunk.byte_count,
                "line_count": chunk.line_count,
                "token_count": chunk.token_count,
                "sha256": chunk.sha256,
                "turn_ids": chunk.turn_ids,
                "overlap_turn_ids": chunk.overlap_turn_ids,
                "fragment_ids": chunk.fragment_ids,
            }
            for index, chunk in enumerate(chunks)
        ],
    }
    index_lines = [
        f"# {document.title or 'Chat Conversation'} — Continuity Chunks",
        "",
        "Upload the parts in order. Each part identifies overlap and new content.",
        "",
    ]
    index_lines.extend(f"{index + 1}. [{name}]({name})" for index, name in enumerate(filenames))
    return ChunkBundle(chunks=chunks, index_text="\n".join(index_lines) + "\n", manifest=manifest)


def write_chunk_bundle(bundle: ChunkBundle, destination: Path, *, force: bool = False) -> list[Path]:
    """Write a validated chunk bundle and return every created path."""

    destination = destination.expanduser()
    names = [entry["filename"] for entry in bundle.manifest["chunks"]]
    targets = [destination / name for name in names]
    targets.extend([destination / "index.md", destination / "chunk-manifest.json"])
    existing = [path for path in targets if path.exists()]
    if existing and not force:
        raise ChunkingError(f"Refusing to overwrite existing chunk file: {existing[0]} (use --force)")
    destination.mkdir(parents=True, exist_ok=True)
    for path, chunk in zip(targets, bundle.chunks):
        path.write_text(chunk.text, encoding="utf-8")
    index_path = destination / "index.md"
    manifest_path = destination / "chunk-manifest.json"
    index_path.write_text(bundle.index_text, encoding="utf-8")
    manifest_path.write_text(json.dumps(bundle.manifest, indent=2) + "\n", encoding="utf-8")
    return targets
