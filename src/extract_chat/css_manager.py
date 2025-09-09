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
    color: #e8e8e8;
    background-color: #111111;
    font-family: Arial, sans-serif;
    line-height: 1.2;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
    font-size: 12pt;
}

h1 {
    color: #f8f8f8;
    font-size: 24pt;
}

h2 {
    color: #efefef;
    margin-top: 30px;
    font-size: 18pt;
}

h3 {
    color: #efefef;
    margin-top: 20px;
    font-size: 14pt;
}

pre {
    background-color: #303030;
    padding: 5px;
    border-radius: 5px;
    overflow-x: auto;
    font-size: 10pt;
    line-height: 1;
    margin: 0.5em 0;
    font-family: monospace;
    white-space-collapse: preserve;
    text-wrap-mode: wrap;
}

code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 10pt;
    line-height: 1.0;
    display: block;
    white-space-collapse: preserve;
    text-wrap-mode: wrap;
}

ul, ol {
    margin: 10px 0;
    padding-left: 20px;
}

li {
    margin: 5px 0;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
    background-color: #222;
}

th, td {
    border: 1px solid #444;
    padding: 8px;
    text-align: left;
}

th {
    background-color: #333;
    color: #fff;
}

tr:nth-child(even) {
    background-color: #2a2a2a;
}

tr:nth-child(odd) {
    background-color: #222;
}

.timestamp {
    color: #cecece;
    font-size: 9pt;
    margin: 5px 0;
}

details {
    margin: 10px 0;
    padding: 10px;
    background-color: #222244;
    border: 1px solid #444;
    border-radius: 5px;
}

details summary {
    cursor: pointer;
    color: #92c1f7;
    font-weight: bold;
    margin: -10px;
    padding: 10px;
    background-color: #1a1a2a;
    border-bottom: 1px solid #444;
}

details[open] summary {
    margin-bottom: 10px;
}

.tool-message {
    background-color: #222244;
    border: 1px solid #444;
    padding: 10px;
    margin: 10px 0;
    border-radius: 5px;
}

.error-message {
    background-color: #442222;
    border: 1px solid #844;
    padding: 10px;
    margin: 10px 0;
    border-radius: 5px;
}

.block {
    margin-bottom: 25px;
    padding: 20px;
    border-radius: 8px;
    border-left: 4px solid #444;
    background-color: #222;
}

.user-block {
    border-left-color: #3498db;
    background-color: #1e3a5f;
}

.assistant-block {
    border-left-color: #27ae60;
    background-color: #1e4d2e;
}

.tool-block {
    border-left-color: #f39c12;
    background-color: #4d3a1e;
    margin-left: 20px;
}

.system-block {
    border-left-color: #e74c3c;
    background-color: #4d1e1e;
}

.block-header {
    font-weight: bold;
    margin-bottom: 10px;
    color: #f8f8f8;
}

.content {
    white-space: pre-wrap;
    word-wrap: break-word;
}

.code-block {
    background: #303030;
    color: #e8e8e8;
    padding: 15px;
    border-radius: 5px;
    overflow-x: auto;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    margin: 10px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}

.tool-call {
    background: #3a3a3a;
    border: 1px solid #555;
    border-radius: 5px;
    padding: 10px;
    margin: 5px 0;
}

.tool-input, .tool-output {
    background: #2d2d2d;
    padding: 8px;
    border-radius: 3px;
    margin: 5px 0;
    border: 1px solid #555;
}

/* Responsive design */
@media (max-width: 768px) {
    body {
        padding: 10px;
        font-size: 14px;
    }
    
    .block {
        padding: 12px;
        margin-bottom: 20px;
    }
    
    .code-block {
        padding: 12px;
        font-size: 12px;
    }
}

/* Print styles */
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
    }
}
"""


def get_css_content(css_file_path: Optional[str] = None) -> str:
    """
    Get CSS content from file or return default.
    
    Args:
        css_file_path: Optional path to custom CSS file
        
    Returns:
        CSS content as string
    """
    if css_file_path and os.path.exists(css_file_path):
        try:
            with open(css_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read CSS file {css_file_path}: {e}")
    
    return get_default_css_content()


def write_css_file(output_path: str, css_content: Optional[str] = None) -> str:
    """
    Write CSS content to a file.
    
    Args:
        output_path: Path where CSS file should be written
        css_content: CSS content to write (uses default if None)
        
    Returns:
        Path to the written CSS file
    """
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
    """
    Get the CSS file path for a given HTML file.
    
    Args:
        html_file_path: Path to HTML file
        
    Returns:
        Path to corresponding CSS file
    """
    html_path = Path(html_file_path)
    css_path = html_path.with_suffix('.css')
    return str(css_path)


def create_external_css_link(css_file_path: str) -> str:
    """
    Create an HTML link tag for external CSS.
    
    Args:
        css_file_path: Path to CSS file
        
    Returns:
        HTML link tag string
    """
    return f'<link rel="stylesheet" type="text/css" href="{css_file_path}">'


def create_inline_css_style(css_content: str) -> str:
    """
    Create an HTML style tag with inline CSS.
    
    Args:
        css_content: CSS content to include
        
    Returns:
        HTML style tag string
    """
    return f'<style>\n{css_content}\n</style>'
