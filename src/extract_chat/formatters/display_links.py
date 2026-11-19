"""Remove a tracking parameter from displayed links, not recorded payloads."""

from html import escape, unescape
from html.parser import HTMLParser
from collections.abc import Callable
from pathlib import PurePosixPath
import re
from urllib.parse import unquote_plus, urlsplit

from markdown_it.helpers import parseLinkDestination

from extract_chat.schemas.render_models import MediaItem


def clean_link_url(url: str) -> str:
    """Keep other query bytes/order, fragments, and non-HTTP paths untouched."""
    if not url.lower().startswith(("https://", "http://")):
        return url
    head, fragment_mark, fragment = url.partition("#")
    base, query_mark, query = head.partition("?")
    if not query_mark:
        return url
    parameters = query.split("&")
    kept = [part for part in parameters if unquote_plus(part.partition("=")[0]).lower() != "utm_source"]
    if kept == parameters:
        return url
    return base + ("?" + "&".join(kept) if kept else "") + fragment_mark + fragment


_ATTRIBUTE = re.compile(r'''(?P<prefix>(?<![\w:-])(?:href|src)\s*=\s*)(?P<quote>["'])(?P<url>.*?)(?P=quote)''', re.I | re.S)


def _clean_tag(tag: str) -> str:
    def replace(match: re.Match[str]) -> str:
        original = unescape(match["url"])
        cleaned = clean_link_url(original)
        return match[0] if original == cleaned else match["prefix"] + match["quote"] + escape(cleaned, quote=True) + match["quote"]
    return _ATTRIBUTE.sub(replace, tag)


class _LinkCleaner(HTMLParser):
    def __init__(self, *, open_new_tabs: bool = False) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.anchor: tuple[int, str] | None = None
        self.open_new_tabs = open_new_tabs

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        markup = _clean_tag(self.get_starttag_text())
        if tag == "a" and self.open_new_tabs:
            href = (dict(attrs).get("href") or "").strip()
            try:
                scheme = urlsplit(href).scheme.lower()
            except ValueError:
                scheme = "invalid"
            if href and not href.startswith("#") and scheme in {"", "http", "https", "file"}:
                attributes = [(key, clean_link_url(value) if key == "href" and value else value) for key, value in attrs if key not in {"target", "rel"}]
                rel = [value for value in (dict(attrs).get("rel") or "").split() if value.lower() not in {"opener", "noopener", "noreferrer"}]
                attributes.extend([("target", "_blank"), ("rel", " ".join(rel + ["noopener", "noreferrer"]))])
                markup = "<a" + "".join(f' {key}="{escape(value, quote=True)}"' if value is not None else f" {key}" for key, value in attributes) + ">"
        self.parts.append(markup)
        if tag == "a":
            self.anchor = (len(self.parts), dict(attrs).get("href") or "")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(_clean_tag(self.get_starttag_text()))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.anchor is not None:
            start, original = self.anchor
            # URL-only labels should agree with their cleaned destinations.
            if unescape("".join(self.parts[start:])) == original:
                self.parts[start:] = [escape(clean_link_url(original), quote=False)]
            self.anchor = None
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")


def clean_html_links(text: str, *, open_new_tabs: bool = False) -> str:
    """Clean displayed URLs; optionally isolate outgoing navigation from anchors."""
    parser = _LinkCleaner(open_new_tabs=open_new_tabs)
    parser.feed(text)
    parser.close()
    return "".join(parser.parts)


_MARKDOWN_URL = re.compile(r"(?P<prefix>\]\(\s*<?|^ {0,3}\[[^\]\n]+\]:\s*<?|<|\[)(?P<url>https?://)", re.I | re.M)


def _clean_markdown_span(text: str) -> str:
    changes: list[tuple[int, int, str]] = []
    for match in _MARKDOWN_URL.finditer(text):
        start = match.start("url")
        end, depth = start, 0
        while end < len(text):
            char = text[end]
            if char.isspace() or char in '<>"' or (char == "]" and match["prefix"] == "["):
                break
            if char == "\\" and end + 1 < len(text):
                end += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                if not depth:
                    break
                depth -= 1
            end += 1
        original = text[start:end]
        cleaned = clean_link_url(original)
        if cleaned != original:
            changes.append((start, end, cleaned))
    for start, end, value in reversed(changes):
        text = text[:start] + value + text[end:]
    return re.sub(r"<[^>\n]+>", lambda match: _clean_tag(match[0]), text)


def _clean_inline_links(text: str, transform: Callable[[str], str] = _clean_markdown_span) -> str:
    result = []
    cursor = 0
    for opening in re.finditer(r"`+", text):
        if opening.start() < cursor:
            continue
        closing = re.search(r"(?<!`)" + re.escape(opening[0]) + r"(?!`)", text[opening.end():])
        if closing is None:
            continue
        end = opening.end() + closing.end()
        result.extend([transform(text[cursor:opening.start()]), text[opening.start():end]])
        cursor = end
    result.append(transform(text[cursor:]))
    return "".join(result)


def clean_markdown_links(text: str, *, transform: Callable[[str], str] = _clean_markdown_span) -> str:
    """Clean link markup outside fenced/indented code and inline backticks."""
    result, prose = [], []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        delimiter = re.match(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if fence:
            result.append(line)
            if delimiter and delimiter[1][0] == fence[0] and len(delimiter[1]) >= fence[1] and not delimiter[2].strip():
                fence = None
            continue
        if delimiter or line.startswith(("    ", "\t")):
            result.extend([_clean_inline_links("".join(prose), transform), line])
            prose = []
            if delimiter:
                fence = (delimiter[1][0], len(delimiter[1]))
        else:
            prose.append(line)
    result.append(_clean_inline_links("".join(prose), transform))
    return "".join(result)


def rewrite_artifact_links(text: str, resolve: Callable[[str, str], str | None]) -> str:
    """Resolve actual Markdown sandbox links, leaving recorded code untouched."""
    def transform(span: str) -> str:
        edits = []
        for match in re.finditer(r'!?\[([^\]\n]+)\]\(\s*', span):
            destination = parseLinkDestination(span, match.end(), len(span))
            if not destination.ok or not destination.str.startswith("sandbox:/"):
                continue
            close = re.match(r'''\s*(?:"[^"\n]*"|'[^'\n]*')?\s*\)''', span[destination.pos:])
            if close is None:
                continue
            end = destination.pos + close.end()
            resolved = resolve(destination.str, match[1])
            replacement = f'{span[match.start():match.end()]}{resolved}{span[destination.pos:end]}' if resolved else f'{match[1]} (not captured)'
            edits.append((match.start(), end, replacement))
        for start, end, value in reversed(edits):
            span = span[:start] + value + span[end:]
        return span
    return clean_markdown_links(text, transform=transform)


def partition_media_items(items: list[MediaItem], references: dict | None = None) -> tuple[list[MediaItem], list[MediaItem]]:
    """Separate files from web URLs; don't repeat already-cited web sources."""
    cited = {clean_link_url(str(ref.get("url"))) for ref in (references or {}).get("references", []) if ref.get("url")}
    artifacts, links, seen = [], [], set()
    file_suffixes = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".avif", ".mp3", ".wav", ".mp4", ".pdf", ".zip", ".lgpt", ".csv", ".tsv", ".xlsx", ".docx", ".pptx"}
    for item in items:
        url = str(item.url or item.label)
        generic_web = item.kind in {"url", "content_url"} and url.startswith(("http://", "https://")) and not item.metadata.get("local_path") and not item.metadata.get("canonical_id")
        if generic_web and clean_link_url(url) in cited:
            continue
        try:
            suffix = PurePosixPath(urlsplit(url).path).suffix.lower() if generic_web else ""
        except ValueError:
            suffix = ""
        if generic_web and suffix not in file_suffixes and not item.metadata.get("image_generation") and not str(item.metadata.get("mime_type") or "").startswith(("image/", "audio/", "video/")):
            key = clean_link_url(url)
            if key not in seen:
                links.append(item)
                seen.add(key)
        else:
            artifacts.append(item)
    return artifacts, links


def render_related_links(items: list[MediaItem]) -> str:
    rows = []
    for item in items:
        url = clean_link_url(str(item.url or item.label))
        label = str(item.metadata.get("title") or item.label)
        if label == str(item.url or item.label):
            label = clean_link_url(label)
        rows.append(f'<li><a href="{escape(url, quote=True)}">{escape(label)}</a></li>')
    return '<details class="related-links"><summary>Related links</summary>\n\n<ul>' + "\n".join(rows) + "</ul>\n\n</details>"


def render_unavailable_artifact(item: MediaItem) -> str:
    return f'<p><strong>{escape(item.label)}</strong> — Not captured</p>\n<p>{escape(str(item.metadata["unavailable_reason"]))}</p>\n<p>Source locator: <code>{escape(str(item.metadata.get("source_locator") or ""))}</code></p>'
