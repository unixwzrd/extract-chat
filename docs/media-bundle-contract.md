# Media Bundle Contract

This document defines the shared file layout between `LogGPT Plus` and `extract-chat`.

## Purpose

`LogGPT Plus` runs inside an authenticated ChatGPT Safari session and can download media while that session is live. `extract-chat` stays offline-first and consumes the exported files later.

## File Naming

For a conversation stem `<stem>`:

- `<stem>.json`
- `<stem>.media.zip`

If the media bundle is extracted, the preferred layout is:

- `<stem>/media/`
- optional `<stem>/media-manifest.json`

## Identity Rules

The canonical media key should be one of:

- `file_*`
- `file-*`
- normalized `file-service://file-*`

Signed estuary or backend URLs should be preserved as metadata, but should not be used as the primary stable identity.

## media-manifest.json

Recommended top-level shape:

```json
{
  "product": "LogGPT Plus",
  "source_file": "2025-02-24_example.json",
  "conversation_title": "Example Conversation",
  "conversation_id": "abc123",
  "exported_at": "2026-03-22T12:34:56Z",
  "item_count": 2,
  "items": [
    {
      "canonical_id": "file_abc123",
      "asset_pointer": "file-service://file_abc123",
      "source_url": "https://chatgpt.com/backend-api/estuary/content?id=file_abc123&...",
      "original_filename": "uploaded-image.png",
      "saved_filename": "file_abc123.png",
      "relative_path": "media/file_abc123.png",
      "mime_type": "image/png",
      "width": 1024,
      "height": 1024,
      "size": 123456,
      "turn_id": "turn-1",
      "message_id": "message-1",
      "role": "user",
      "content_type": "multimodal_text",
      "download_status": "downloaded",
      "failure_reason": null
    }
  ]
}
```

## ZIP Layout

Recommended ZIP contents:

- `media-manifest.json`
- `media/<file-id>.<ext>`

The extracted directory should preserve the same relative paths recorded in the manifest.

## extract-chat Behavior

When `extract-chat` finds:

- `<stem>/media/`
- optional `<stem>/media-manifest.json`

it will:

1. match turn-level media entries by canonical media id first
2. prefer local media links in rendered Markdown/HTML
3. preserve the original remote URL as metadata when available

Current limitation:

- `extract-chat` does not auto-extract `<stem>.media.zip` yet
