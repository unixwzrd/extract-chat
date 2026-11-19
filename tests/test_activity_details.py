"""Readable JSON fields must not corrupt literal escapes or activate payloads."""

from html import escape
import json

import pytest

from extract_chat.formatters.activity_details import _numbered_lines, _readable_json, _unescape_heredoc_quotes, render_activity_details, render_json_payload
from extract_chat.formatters.html_formatter import HTMLFormatter
from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.css_manager import get_default_css_content
from extract_chat.schemas.render_models import RenderDocument, RenderTurn, ToolActivityItem


def test_default_code_css_preserves_lines_and_scrolls_without_changing_text() -> None:
    css = get_default_css_content()
    pre = css.split("pre {", 1)[1].split("}", 1)[0]
    assert "white-space: pre;" in pre
    assert "overflow-x: auto;" in pre
    text = "file-with-dashes-" + "a" * 240 + "\n    indented line\n"
    item = ToolActivityItem(category="tool_output", title="Result", content=text, metadata={"presentation": "native"})
    rendered = render_activity_details([item], html=True)
    assert escape(text) in rendered
    assert "<script" not in rendered


@pytest.mark.parametrize("html", [False, True])
def test_json_command_display_decodes_only_one_layer(html: bool) -> None:
    command = 'printf "hello"\nprintf "\\n"\nprintf "\\\\"\n# café → 日本語'
    raw = json.dumps({"command": command, "cwd": r"C:\new\folder", "timeout": 20})
    output = render_json_payload(raw, html=html)
    assert output is not None
    displayed = command.replace("\n", "\n" + " " * 14)
    assert (escape(displayed) if html else displayed) in output
    assert (escape('"command": "') if html else '"command": "') in output
    assert (escape(raw) if html else raw) in output
    assert r"C:\new\folder" in output
    assert "Raw JSON" in output
    assert raw == json.dumps({"command": command, "cwd": r"C:\new\folder", "timeout": 20})


@pytest.mark.parametrize("raw", [r'print("keep\nthis")', '"a JSON string, not tool fields"', '{"bad":', '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_nonstandard_or_nonobject_content_is_not_rewritten(raw: str) -> None:
    assert render_json_payload(raw, html=False) is None
    assert render_json_payload(raw, html=True) is None


def test_nested_fields_arrays_and_empty_values_remain_available() -> None:
    raw = json.dumps({"nested": {"args": ['line1\nline2', r"literal\n", False, None]}, "empty": {}, "list": []})
    output = render_json_payload(raw, html=False)
    assert output is not None
    for expected in ('"nested": {', '"args": [', "line1\n       line2", r"literal\n", "false", "null", "{}", "[]"):
        assert expected in output
    assert "nested › args[0]" not in output


def test_html_and_markdown_payloads_remain_inert() -> None:
    text = '</code></pre><script>alert("x")</script>\n```\ncode'
    raw = json.dumps({"<img onerror=alert(1)>": text})
    html = render_json_payload(raw, html=True)
    markdown = render_json_payload(raw, html=False)
    assert html and markdown
    assert "<script>" not in html and "<img onerror" not in html
    assert all(escape(line) in html for line in text.split("\n"))
    assert "````text" in markdown


@pytest.mark.parametrize("source", ["hermes", None])
def test_all_sources_share_readable_tool_fields_without_rewriting_thoughts(source: str | None) -> None:
    command = 'echo "hello"\necho "\\n"'
    raw = json.dumps({"command": command})
    tools = [
        ToolActivityItem(category="tool_call", title="Tool Call", content=raw, metadata={"source": source, "recipient": "terminal", "request_id": "call1"}),
        ToolActivityItem(category="reasoning", title="Thought", content=raw, metadata={"source": source}),
    ]
    doc = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="answer", content="Visible answer", tools_used=tools)])
    for formatter, expected in [(MarkdownFormatter(), command), (HTMLFormatter(), escape(command))]:
        output = formatter.format_document(doc)
        assert all(line in output for line in expected.split("\n")) and "Raw JSON" in output
        assert output.count("<summary>Raw JSON</summary>") == 1, "The thought must retain its original text rather than being decoded as tool fields"
    if source == "hermes":
        thought = render_activity_details([tools[1]], html=True)
        assert "Raw JSON" not in thought and escape(raw) in thought


def test_pathological_payloads_fall_back_without_losing_raw_data() -> None:
    assert render_json_payload(json.dumps(list(range(300))), html=False) is None
    assert render_json_payload("[" * 100 + "0" + "]" * 100, html=True) is None


@pytest.mark.parametrize("html", [False, True])
@pytest.mark.parametrize("mode", ["raw", "pretty"])
def test_escaped_json_modes_keep_newline_escapes(html: bool, mode: str) -> None:
    value = {"command": 'echo "hello"\nprintf "\\n"', "path": r"C:\new\folder"}
    raw = json.dumps(value)
    expected = raw if mode == "raw" else json.dumps(value, ensure_ascii=False, indent=2)
    rendered = render_json_payload(raw, html=html, mode=mode)
    assert (escape(expected) if html else expected) in rendered
    assert "Raw JSON" not in rendered
    assert value["command"] not in rendered


@pytest.mark.parametrize("source", ["hermes", None])
def test_json_mode_is_shared_by_both_formatters_and_does_not_touch_thoughts(source: str | None) -> None:
    command = 'echo "hello"\necho "done"'
    raw = json.dumps({"command": command})
    tools = [ToolActivityItem(category="tool_call", title="Call", content=raw, metadata={"source": source, "request_id": "call", "recipient": "terminal"})]
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="a", tools_used=tools)])
    for formatter in [HTMLFormatter, MarkdownFormatter]:
        output = formatter({"tool_json": "raw"}).format_document(document)
        assert command not in output
        assert "Raw JSON" not in output
        assert r"\n" in output


def test_readable_mode_decodes_returned_file_content_as_well_as_arguments() -> None:
    content = '1|# Example\n2|\n3|Command: echo "hello"\n4|Literal escape: \\n\n5|Path: C:\\new\\folder'
    argument = json.dumps({"path": "/example/README.md"})
    result = json.dumps({"content": content, "total_lines": 5, "is_binary": False})
    tools = [ToolActivityItem(category=kind, title=label, content=value, metadata={"source": "hermes", "request_id": "read1", "recipient": "read_file"}) for kind, label, value in [("tool_call", "Call", argument), ("tool_output", "Result", result)]]
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="a", tools_used=tools)])
    for formatter in [MarkdownFormatter, HTMLFormatter]:
        readable = formatter({"tool_json": "readable"}).format_document(document)
        displayed = _numbered_lines(content).replace("\n", "\n" + " " * 14)
        displayed = "\n".join(line.rstrip() for line in displayed.split("\n"))
        expected = escape(displayed) if formatter is HTMLFormatter else displayed
        assert expected in readable
        assert "Readable JSON (decoded strings) + Raw JSON" in readable
        assert "<summary>Raw JSON</summary>" in readable
        assert "Formatted JSON (escaped)" in formatter({"tool_json": "pretty"}).format_document(document)


def test_human_json_keeps_boundaries_and_unescapes_only_string_values() -> None:
    value = {"command": 'echo "one"\necho "\\n"', "exit_code": 0, "error": None}
    expected = '{\n  "command": "echo "one"\n              echo "\\n"",\n  "exit_code": 0,\n  "error": null\n}'
    assert _readable_json(value) == expected
    assert value["command"] == 'echo "one"\necho "\\n"'


def test_numbered_file_lines_align_without_erasing_code_indentation() -> None:
    text = '8|plain\n9|    indented\n10|"quoted"\n11|\n'
    assert _numbered_lines(text) == ' 8 | plain\n 9 |     indented\n10 | "quoted"\n11 | \n'
    for text in ['echo foo | sed bar', '1|one', '1|one\n3|three', 'first\n2|second', '1 | already spaced\n2 | already spaced']:
        assert _numbered_lines(text) == text


@pytest.mark.parametrize("formatter", [HTMLFormatter, MarkdownFormatter])
@pytest.mark.parametrize("quoted", [False, True])
def test_heredoc_quotes_are_unescaped_in_place_without_extra_views(formatter, quoted: bool) -> None:
    value = {"uploads": [{"local_path": "/scratch/日本語/chart.png", "purpose": "create_library_file"}], "pattern": r"\d+\n", "content": 'first\nsecond', "literal": r"C:\new\folder", "inert": '</code><script>bad()</script>\n```\n$(not_executed)'}
    raw = json.dumps(value, ensure_ascii=False)
    shell_quoted = raw.replace('"', '\\"')
    command = 'bash -lc "python3 upload.py <<\'JSON\'\n' + shell_quoted + '\nJSON"' if quoted else "python3 upload.py <<'JSON'\n" + raw + "\nJSON"
    normalized = command.replace(shell_quoted, raw) if quoted else command
    item = ToolActivityItem(category="tool_call", title="Tool call: container.exec", content=command, metadata={"presentation": "native", "tool_name": "container.exec"})
    document = RenderDocument(turns=[RenderTurn(role="assistant", turn_id="a", tools_used=[item])])
    rendered = formatter({"tool_json": "readable"}).format_document(document)
    expected = escape(normalized) if formatter is HTMLFormatter else normalized
    assert expected in rendered
    assert "Embedded JSON" not in rendered
    assert "Display only:" not in rendered
    if formatter is HTMLFormatter:
        assert "<script>" not in rendered
    assert item.content == command
    for mode in ("pretty", "raw"):
        unchanged = formatter({"tool_json": mode}).format_document(document)
        assert (escape(command) if formatter is HTMLFormatter else command) in unchanged
        assert "Embedded JSON" not in unchanged


def test_heredoc_retains_required_nested_quotes_and_other_backslashes() -> None:
    original = r'{\"quoted\":\"say \\\"hello\\\"\",\"literal\":\"\\n\",\"path\":\"C:\\new\\folder\"}'
    expected = r'{"quoted":"say \"hello\"","literal":"\\n","path":"C:\\new\\folder"}'
    command = "python3 upload.py <<'JSON'\n" + original + "\nJSON"
    assert _unescape_heredoc_quotes(command) == "python3 upload.py <<'JSON'\n" + expected + "\nJSON"
    assert json.loads(expected)["quoted"] == 'say "hello"'


@pytest.mark.parametrize("body", ['{"x":1,"x":2}', '{"x":NaN}', '{"broken":', '"not an object"', '[' * 100 + '0' + ']' * 100])
def test_invalid_embedded_json_is_not_repaired_or_reinterpreted(body: str) -> None:
    command = "python3 upload.py <<'JSON'\n" + body + "\nJSON"
    item = ToolActivityItem(category="tool_call", title="Call", content=command, metadata={"presentation": "native"})
    output = render_activity_details([item], html=True)
    assert escape(command) in output
    assert "Embedded JSON — readable view" not in output


def test_ordinary_python_and_shell_escapes_remain_exactly_as_exported() -> None:
    code = 'import re\nprint("say \\"hello\\"", r"\\d+", "\\n")\n'
    compile(code, "recorded-example.py", "exec")  # Syntax check only, never run.
    command = "python3 - <<'PY'\n" + code + "PY"
    item = ToolActivityItem(category="tool_call", title="Call", content=command, language="python", metadata={"presentation": "native"})
    output = render_activity_details([item], html=True)
    assert escape(command) in output
    assert "Embedded JSON" not in output
