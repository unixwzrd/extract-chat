"""Tracking cleanup is presentation-only and must preserve recorded code."""

from html import escape

import pytest

from extract_chat.formatters.display_links import clean_html_links, clean_link_url, clean_markdown_links, partition_media_items
from extract_chat.schemas.render_models import MediaItem


def test_outgoing_navigation_opens_new_tabs_but_fragments_stay_local():
    source = '<a href="https://example.org/?utm_source=chatgpt.com&amp;x=1" target="_self" rel="opener nofollow">Source</a><a href="artifacts/image.png">Image</a><a href="report.pdf" download>File</a><a href="#ref-target-1">[1]</a><a id="local"></a><pre><code>&lt;a href="file.txt"&gt;</code></pre>'
    output = clean_html_links(source, open_new_tabs=True)
    assert 'href="https://example.org/?x=1" target="_blank" rel="nofollow noopener noreferrer"' in output
    assert 'href="artifacts/image.png" target="_blank" rel="noopener noreferrer"' in output
    assert 'href="report.pdf" download target="_blank"' in output
    assert '<a href="#ref-target-1">[1]</a>' in output
    assert '<a id="local"></a>' in output
    assert '&lt;a href="file.txt"&gt;' in output
    assert clean_html_links(output, open_new_tabs=True) == output


def test_web_sources_are_related_links_not_artifacts_or_duplicate_citations():
    cited = MediaItem(kind="url", label="source", url="https://example.org/source?utm_source=chatgpt.com")
    other = MediaItem(kind="url", label="other", url="https://example.org/other")
    image = MediaItem(kind="asset_pointer", label="picture", url="artifacts/picture.png", metadata={"local_path": "artifacts/picture.png"})
    artifacts, links = partition_media_items([cited, other, other, image], {"references": [{"url": "https://example.org/source"}]})
    assert artifacts == [image]
    assert links == [other]


@pytest.mark.parametrize(("source", "expected"), [
    ("https://example.org/page?utm_source=chatgpt.com", "https://example.org/page"),
    ("https://example.org/?v=a%2Bb&utm_source=chatgpt.com&token=a+b#part", "https://example.org/?v=a%2Bb&token=a+b#part"),
    ("https://example.org/?UTM_SOURCE=x&v=one&v=two&utm_source=y", "https://example.org/?v=one&v=two"),
    ("https://example.org/?%75tm_source=x#utm_source=keep", "https://example.org/#utm_source=keep"),
    ("https://example.org/?utm_campaign=keep&signature=abc%2F123", "https://example.org/?utm_campaign=keep&signature=abc%2F123"),
    ("file:///tmp/name?utm_source=literal", "file:///tmp/name?utm_source=literal"),
    ("artifacts/name?utm_source=literal.png", "artifacts/name?utm_source=literal.png"),
])
def test_only_requested_query_parameter_is_removed(source: str, expected: str) -> None:
    assert clean_link_url(source) == expected


def test_html_links_and_url_labels_are_clean_but_code_is_untouched() -> None:
    url = "https://example.org/?v=one&utm_source=chatgpt.com#part"
    encoded = escape(url, quote=True)
    source = f'<a href="{encoded}">{encoded}</a><pre><code>{encoded}</code></pre><a href="#ref-target-1">[1]</a>'
    output = clean_html_links(source)
    assert '<a href="https://example.org/?v=one#part">https://example.org/?v=one#part</a>' in output
    assert f'<pre><code>{encoded}</code></pre>' in output
    assert '<a href="#ref-target-1">[1]</a>' in output


def test_markdown_destinations_titles_autolinks_and_balanced_parentheses() -> None:
    text = '[entry](https://example.org/Page_(Name)?utm_source=x "Title")\n[ref]: <https://example.org/?utm_source=x&v=1>\n<https://example.org/?utm_source=x>\n[https://example.org/?utm_source=x](https://example.org/?utm_source=x)'
    output = clean_markdown_links(text)
    assert '[entry](https://example.org/Page_(Name) "Title")' in output
    assert '[ref]: <https://example.org/?v=1>' in output
    assert '<https://example.org/>' in output
    assert '[https://example.org/](https://example.org/)' in output
    assert "utm_source" not in output


def test_markdown_tool_payloads_inline_and_indented_code_are_not_changed() -> None:
    link = '[example](https://example.org/?utm_source=x)'
    for protected in [f'```json\n{{"command": "{link}"}}\n```\n', f'~~~~text\n{link}\n~~~~\n', f'`{link}`', f'``line one\n{link}\nline three``', f'    {link}\n']:
        assert clean_markdown_links(protected) == protected
    assert clean_markdown_links(f'`{link}` and {link}').endswith('and [example](https://example.org/)')
