"""Native metadata is meaningful activity, not a flat dump or fake media."""

from copy import deepcopy

import pytest

from extract_chat.context.document_context import DocumentContext
from extract_chat.artifact_package import attach_local_artifacts
from extract_chat.formatters.html_formatter import HTMLFormatter
from extract_chat.formatters.markdown_formatter import MarkdownFormatter
from extract_chat.processors.turn_processor import TurnProcessorV2
from extract_chat.schemas.conversation import Conversation


def record(uid, parent, role, content, *, tool=None, recipient="all", channel=None, metadata=None, timestamp=1):
    return {"id": uid, "parent": parent, "message": {
        "id": uid, "author": {"role": role, "name": tool}, "content": content,
        "create_time": timestamp, "recipient": recipient, "channel": channel,
        "metadata": metadata or {},
    }}


def process(nodes):
    conversation = Conversation.model_validate({"mapping": {node["id"]: node for node in nodes}})
    try:
        DocumentContext.initialize(conversation=conversation)
        return TurnProcessorV2().process_conversation(conversation)
    finally:
        DocumentContext.reset()


def test_context_attribution_and_reasoning_recap_survive_without_becoming_media():
    citations = [{"citation": {"type": "conversation_context_citation", "attribution": "Past chat", "title": "Earlier conversation", "url": "/c/abc", "snippet": "Exported excerpt"}}, {"citation": {"type": "conversation_context_citation", "attribution": "Memory", "title": "Remembered preference", "url": "#settings/Personalization", "snippet": "Preference text"}}]
    nodes = [record("u", None, "user", {"parts": ["Question"]}), record("t", "u", "assistant", {"content_type": "thoughts", "thoughts": []}, timestamp=2), record("r", "t", "assistant", {"content_type": "reasoning_recap", "content": "Worked for 2m 21s"}, timestamp=3), record("a", "r", "assistant", {"parts": ["Answer"]}, channel="final", timestamp=4, metadata={"model_slug": "model-A", "conversation_context_citation_metadata": citations})]
    before = deepcopy(nodes)
    document = process(nodes)
    answer = document.turns[-1]
    assert not answer.media_items
    assert [item.content for item in answer.tools_used] == ["", "Worked for 2m 21s"]
    for formatter in (HTMLFormatter, MarkdownFormatter):
        output = formatter().format_document(document)
        assert "Context used (2 citations)" in output
        assert 'href="https://chatgpt.com/c/abc"' in output
        assert 'href="https://chatgpt.com/#settings/Personalization"' not in output
        assert "Memory: Remembered preference" in output
        assert "Exported excerpt" in output and "Preference text" in output
        assert "Worked for 2m 21s" in output
        assert "No reasoning text was included" in output
        assert "model-A" in output
        assert "Tool call:" not in output
    assert nodes == before


def test_named_command_and_result_pair_through_progress_with_metadata():
    common = {"turn_exchange_id": "exchange", "model_slug": "model-A"}
    nodes = [
        record("u", None, "user", {"parts": ["Question"]}),
        record("p", "u", "assistant", {"parts": ["Working"]}, channel="commentary", metadata=common, timestamp=2),
        record("call", "p", "assistant", {"content_type": "code", "language": "sh", "text": "echo hello"}, recipient="container.exec", metadata=common, timestamp=3),
        record("progress", "call", "assistant", {"parts": ["Still working"]}, channel="commentary", metadata=common, timestamp=4),
        record("result", "progress", "tool", {"content_type": "execution_output", "text": "hello\n"}, tool="container.exec", metadata={**common, "work_activity": {"groups": [{"items": [{"kind": "command", "count": 1, "status": "completed"}]}]}}, timestamp=5),
        record("a", "result", "assistant", {"parts": ["Done"]}, channel="final", metadata={**common, "model_slug": "model-B"}, timestamp=6),
    ]
    document = process(nodes)
    assert len(document.turns) == 2
    answer = document.turns[-1]
    call, result = [item for item in answer.tools_used if item.category in {"tool_call", "tool_output"}]
    assert call.metadata["pair_id"] == result.metadata["pair_id"] == "call"
    assert result.metadata["tool_name"] == "container.exec"
    for formatter in (HTMLFormatter, MarkdownFormatter):
        output = formatter().format_document(document)
        assert output.count("<summary>Tool call: container.exec — 1 result recorded</summary>") == 1
        assert "Result / output" in output
        assert "echo hello" in output and "hello" in output
        assert "Recorded work:" in output and "completed" in output
        assert "model-A" in output and "model-B" in output
        assert "Exported fields" in output
        assert "Still working" in output and "Working" in output
        assert "Tool Output: all" not in output


def test_structured_thoughts_and_analysis_are_readable_and_not_python_repr():
    thought = {"summary": "Planning", "content": "**Planning**", "chunks": [{"text": "Actual exported reasoning"}]}
    document = process([record("t", None, "assistant", {"content_type": "thoughts", "thoughts": [thought]}), record("analysis", "t", "assistant", {"parts": ["Analysis text"]}, channel="analysis", timestamp=2), record("a", "analysis", "assistant", {"parts": ["Answer"]}, timestamp=3)])
    assert len(document.turns) == 1
    assert document.turns[0].tools_used[0].content == "**Planning**\n\nActual exported reasoning"
    html = HTMLFormatter().format_document(document)
    assert "<strong>Planning</strong>" in html and "Actual exported reasoning" in html
    assert "[{'summary'" not in html
    assert "Analysis text" in html


@pytest.mark.parametrize("mismatch", ["branch", "user", "call-id"])
def test_pairing_never_uses_time_alone(mismatch):
    nodes = [record("u", None, "user", {"parts": ["Question"]}), record("call", "u", "assistant", {"content_type": "code", "text": "run"}, recipient="model.delegate", metadata={"tool_call_id": "id1"}, timestamp=2)]
    parent = "call"
    if mismatch == "branch":
        parent = "u"
    elif mismatch == "user":
        nodes.append(record("u2", "call", "user", {"parts": ["Next question"]}, timestamp=3))
        parent = "u2"
    nodes.extend([record("output", parent, "tool", {"content_type": "execution_output", "text": "result"}, tool="model.delegate", metadata={"tool_call_id": "id2"} if mismatch == "call-id" else {}, timestamp=4), record("a", "output", "assistant", {"parts": ["Done"]}, timestamp=5)])
    document = process(nodes)
    activities = [item for turn in document.turns for item in turn.tools_used]
    assert len(activities) == 2
    assert all(not item.metadata.get("pair_id") for item in activities)
    assert "No matching call could be established" in HTMLFormatter().format_document(document)


def test_unanswered_activity_is_retained_and_cannot_move_to_next_user_reply():
    nodes = [record("u", None, "user", {"parts": ["First question"]}), record("call", "u", "assistant", {"content_type": "code", "text": "recorded command"}, recipient="tool", timestamp=2), record("u2", "call", "user", {"parts": ["Second question"]}, timestamp=3), record("a", "u2", "assistant", {"parts": ["Second answer"]}, timestamp=4)]
    document = process(nodes)
    assert document.turns[-1].tools_used == []
    orphan = next(turn for turn in document.turns if turn.metadata.get("activity_only"))
    assert orphan.tools_used[0].content == "recorded command"
    assert "Exported activity" in HTMLFormatter().format_document(document)


def test_context_links_and_recorded_commands_cannot_inject_html():
    document = process([record("c", None, "assistant", {"content_type": "code", "text": '</code><script>bad()</script>\n```'}, recipient='tool<img src=x onerror=bad()>'), record("a", "c", "assistant", {"parts": ["Answer"]}, timestamp=2, metadata={"conversation_context_citation_metadata": [{"citation": {"title": "<script>bad()</script>", "url": "javascript:bad()", "snippet": "<img src=x>"}}]})])
    html = HTMLFormatter().format_document(document)
    assert '<script>' not in html and '<img src=x' not in html
    assert 'href="javascript:' not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("formatter", [HTMLFormatter, MarkdownFormatter])
def test_activity_identity_is_labelled_and_commentary_not_reclassified(formatter):
    common = {"turn_exchange_id": "exchange", "model_slug": "model-A"}
    document = process([
        record("p", None, "assistant", {"parts": ["I am creating the files."]}, channel="commentary", metadata=common),
        record("call", "p", "assistant", {"content_type": "code", "text": "run"}, recipient="container.exec", timestamp=2, metadata=common),
        record("result", "call", "tool", {"content_type": "execution_output", "text": "done"}, tool="container.exec", timestamp=3, metadata=common),
        record("a", "result", "assistant", {"parts": ["Done"]}, channel="final", timestamp=4, metadata=common),
    ])
    output = formatter().format_document(document)
    assert "Assistant commentary" in output and "commentary" in output
    for label in ("Author", "Time", "Model", "Turn ID"):
        assert label in output
    assert "Tool: container.exec" in output
    assert "Record:" not in output
    assert " · Model:" not in output
    if formatter is HTMLFormatter:
        assert '<dl class="activity-metadata">' in output
        assert '<dt>Turn ID</dt><dd><code>call</code></dd>' in output
    else:
        assert "| Field | Value |" in output
        assert "| Turn ID | call |" in output


@pytest.mark.parametrize("patch_present", [False, True])
def test_patch_description_exposes_count_limits_without_inventing_files(patch_present):
    patch = "*** Begin Patch\n*** Add File: actual.txt\n+content\n*** End Patch"
    content = {"content_type": "code", "text": "bash -lc apply_patch"}
    if patch_present:
        content["patch"] = patch
    document = process([
        record("call", None, "assistant", content, recipient="container.exec", metadata={"reasoning_title": "Applying a patch to code", "work_activity": {"groups": [{"items": [{"kind": "file-change", "count": 4, "status": "in_progress"}]}]}}),
        record("a", "call", "assistant", {"parts": ["Done"]}, timestamp=2),
    ])
    for formatter in (HTMLFormatter, MarkdownFormatter):
        output = formatter().format_document(document)
        assert "Reported activity:" in output and "Applying a patch to code" in output
        assert "count only, not a file list or individual change types" in output
        assert ("No patch body was included" in output) != patch_present
        assert ("actual.txt" in output) == patch_present


def test_returned_image_prompt_is_linked_to_exact_asset_and_not_arguments(tmp_path):
    prompt = 'Scene: archive robot\nLighting: warm\nLiteral escape: \\n\n<script>not executable</script>'
    parts = [{"content_type": "image_asset_pointer", "asset_pointer": "sediment://file-image", "width": 1254, "height": 1254, "metadata": {"dalle": {"prompt": prompt, "seed": 0, "serialization_title": "DALL-E generation metadata"}, "generation": {"transparent_background": False}}}]
    document = process([
        record("call", None, "assistant", {"content_type": "code", "text": "{}"}, recipient="opaque-image-tool"),
        record("result", "call", "tool", {"content_type": "multimodal_text", "parts": parts}, tool="opaque-image-tool", timestamp=2),
        record("a", "result", "assistant", {"parts": ["Done"]}, timestamp=3),
    ])
    input_path = tmp_path / "chat.json"
    input_path.write_text("{}", encoding="utf-8")
    image = tmp_path / "artifacts/generated/file-image.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"test-image")
    output_path = tmp_path / "output/chat.html"
    attach_local_artifacts(document=document, input_path=input_path, output_path=output_path, artifact_destination=output_path.parent)
    answer = document.turns[-1]
    assert answer.tools_used[0].content == "{}", "Do not move a returned prompt into the recorded call arguments"
    generation = answer.tools_used[1].metadata["images"][0]
    assert generation["local_path"] == "artifacts/generated/file-image.png"
    assert generation["prompt"] == prompt
    assert generation["parameters"]["seed"] == 0
    assert generation["parameters"]["transparent_background"] is False
    assert answer.media_items[0].metadata["image_generation"]["prompt"] == prompt
    for formatter in (HTMLFormatter, MarkdownFormatter):
        output = formatter().format_document(document)
        assert output.count("Image-generation prompt") == 2, "Show prompt with the activity and the captured image"
        assert "returned image metadata.dalle.prompt" in output
        assert "1254 × 1254" in output
        assert 'href="artifacts/generated/file-image.png"' in output
        assert "Scene: archive robot\nLighting: warm" in output
        if formatter is HTMLFormatter:
            assert '<script>' not in output
        else:
            assert '```text\n' + prompt + '\n```' in output, "Markdown source may contain literal tags only inside its safe code fence"
        assert "No text output was exported" not in output


@pytest.mark.parametrize("direct", [False, True])
def test_namespace_tool_result_requires_its_direct_call_parent(direct):
    document = process([
        record("call", None, "assistant", {"content_type": "code", "text": "{}"}, recipient="api_tool.list_resources"),
        record("thought", "call", "assistant", {"content_type": "thoughts", "thoughts": []}, timestamp=2),
        record("output", "call" if direct else "thought", "tool", {"text": "resources"}, tool="api_tool", timestamp=3),
        record("a", "output", "assistant", {"parts": ["Done"]}, timestamp=4),
    ])
    output = next(item for turn in document.turns for item in turn.tools_used if item.turn_id == "output")
    assert bool(output.metadata.get("pair_id")) == direct
    if direct:
        assert output.metadata["pairing"] == "direct parent and tool namespace"
