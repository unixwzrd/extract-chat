"""
CSS management for extract_chat_v2.

This module handles CSS generation and management for HTML output,
providing both default styles and custom CSS file support.
"""

import os
from pathlib import Path
from typing import Optional


def get_default_css_content() -> str:
    """Return the default CSS content for the HTML output."""
    return """body {
    color: #e7ecf6;
    background-color: #111621;
    font-family: 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.55;
    max-width: 980px;
    margin: 0 auto;
    padding: 32px 28px;
    font-size: 13.5pt;
}

h1 {
    color: #f0f6ff;
    font-size: 28pt;
    margin-bottom: 0.25em;
}

h2 {
    color: #d5e2ff;
    margin-top: 36px;
    font-size: 20pt;
}

h3 {
    color: #bed0ff;
    margin-top: 26px;
    font-size: 16pt;
}

pre {
    background-color: #1d2534;
    padding: 10px 14px;
    border-radius: 6px;
    border: 1px solid #2e3a52;
    overflow-x: auto;
    font-size: 10.5pt;
    margin: 0.75em 0;
    font-family: 'Fira Code', 'SFMono-Regular', Menlo, monospace;
    white-space: pre-wrap;
}

code {
    font-family: 'Fira Code', 'SFMono-Regular', Menlo, monospace;
    font-size: 10.5pt;
    background-color: #1d2534;
    padding: 2px 4px;
    border-radius: 4px;
}

ul, ol {
    margin: 12px 0;
    padding-left: 24px;
}

li {
    margin: 6px 0;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 14px 0;
    background-color: #121a27;
    border: 1px solid #2b394f;
}

th, td {
    border: 1px solid #2b394f;
    padding: 10px;
    text-align: left;
}

th {
    background-color: #1b2538;
    color: #dee7ff;
}

tr:nth-child(even) {
    background-color: #151e2c;
}

.timestamp {
    color: #92a1c2;
    font-size: 10pt;
    margin: 6px 0;
}

details {
    margin: 12px 0;
    padding: 12px 16px;
    background-color: #172134;
    border: 1px solid #253148;
    border-radius: 6px;
}

details summary {
    cursor: pointer;
    color: #abc0ff;
    font-weight: 600;
    margin: -12px;
    padding: 12px 16px;
    background-color: #142031;
    border-bottom: 1px solid #253148;
}

details[open] summary {
    margin-bottom: 12px;
}

.tool-message {
    background-color: #1d1d2b;
    border: 1px solid #493f6b;
    padding: 14px;
    margin: 12px 0;
    border-radius: 6px;
}

.error-message {
    background-color: #261a1f;
    border: 1px solid #a15b5b;
    padding: 14px;
    margin: 12px 0;
    border-radius: 6px;
}

.block {
    margin-bottom: 28px;
    padding: 22px 24px;
    border-radius: 10px;
    border-left: 5px solid #2e3a52;
    background-color: #161f2e;
    box-shadow: 0 10px 22px rgba(5, 10, 20, 0.4);
}

.user-block {
    border-left-color: #4f8bff;
    background-color: #16233a;
}

.assistant-block {
    border-left-color: #2fd690;
    background-color: #112c25;
}

.tool-block {
    border-left-color: #f4a261;
    background-color: #2d2116;
    margin-left: 24px;
}

.system-block {
    border-left-color: #ff6b6b;
    background-color: #32161b;
}

.block-header {
    font-weight: 600;
    margin-bottom: 12px;
    color: #e0e8ff;
}

.content {
    white-space: pre-wrap;
    word-wrap: break-word;
}

.code-block {
    background: #0e131f;
    color: #f2f2f2;
    padding: 18px;
    border-radius: 6px;
    overflow-x: auto;
    font-family: 'Fira Code', 'SFMono-Regular', Menlo, monospace;
    margin: 14px 0;
    white-space: pre;
}

.tool-call {
    background: #152032;
    border: 1px solid #263246;
    border-radius: 6px;
    padding: 12px;
}

.references {
    margin-top: 18px;
    padding-left: 24px;
}

.references li {
    margin-bottom: 12px;
}

.references li .excerpt {
    display: block;
    margin-top: 4px;
    color: #c7d2ef;
    font-style: italic;
}

.references li .lines {
    margin-left: 6px;
    color: #9baed7;
}

.references li .backref {
    margin-left: 6px;
    text-decoration: none;
    color: #8fbaff;
}

sup a {
    color: #8fbaff;
    text-decoration: none;
}

a {
    color: #6aa7ff;
}

a:hover {
    color: #3d7ce6;
}

.block + .references {
    margin-top: 24px;
}

.tool-input, .tool-output {
    background: #1c2638;
    padding: 10px;
    border-radius: 6px;
    margin: 6px 0;
    border: 1px solid #2d3b52;
}

@media (max-width: 768px) {
    body {
        padding: 16px;
        font-size: 13px;
    }
    
    .block {
        padding: 16px;
        margin-bottom: 22px;
    }
    
    .code-block {
        padding: 14px;
        font-size: 12px;
    }
}

@media print {
    body {
        background: white;
        color: black;
        max-width: none;
        padding: 0;
    }
    
    .block {
        break-inside: avoid;
        page-break-inside: avoid;
        box-shadow: none;
        border-left-color: #666;
        background-color: #fff;
    }
}
"""


def get_css_content(css_file_path: Optional[str] = None) -> str:
    """Get CSS content from file or return default."""
    if css_file_path and os.path.exists(css_file_path):
        try:
            with open(css_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read CSS file {css_file_path}: {e}")
    return get_default_css_content()


def write_css_file(output_path: str, css_content: Optional[str] = None) -> str:
    """Write CSS content to a file."""
    if css_content is None:
        css_content = get_default_css_content()
    css_path = get_css_file_path(output_path)
    try:
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(css_content)
        return css_path
    except Exception as e:
        print(f"Warning: Could not write CSS file {css_path}: {e}")
        return ""


def get_css_file_path(html_file_path: str) -> str:
    """Get the CSS file path for a given HTML file."""
    html_path = Path(html_file_path)
    css_path = html_path.with_suffix('.css')
    return str(css_path)


def create_external_css_link(css_file_path: str) -> str:
    """Create an HTML link tag for external CSS."""
    return f'<link rel="stylesheet" type="text/css" href="{css_file_path}">'


def create_inline_css_style(css_content: str) -> str:
    """Create an HTML style tag with inline CSS."""
    return f'<style>\n{css_content}\n</style>'
