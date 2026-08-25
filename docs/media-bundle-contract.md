# LogGPT Artifact Archive Contract

This is the language-neutral handoff between LogGPT Plus and extract-chat.
LogGPT Plus captures authenticated conversation data and artifacts. extract-chat
performs offline rendering, output naming, embedded-table derivation, and
continuity chunking.

## Version 2 layout

For a canonical conversation stem `<stem>`:

```text
<stem>.zip
├── <stem>.json
└── <stem>/
    ├── artifact-manifest.json
    └── artifacts/
        ├── generated/
        ├── uploaded/
        └── derived/
```

`uploaded` takes precedence when the same canonical file identifier is also
referenced by a tool. `generated` contains files produced by ChatGPT or its
tools. `derived` contains explicit embedded representations or later offline
derivations for which no equivalent downloaded artifact exists.

## Manifest

The manifest has `format_version: 2` and an `artifacts` array. Each artifact
records, when available:

- `canonical_id`, `asset_pointer`, `origin`, `role`, `content_type`
- `original_filename`, `saved_filename`, and ZIP-relative `relative_path`
- `declared_mime_type` and `detected_mime_type` (`mime_type` remains a
  compatibility alias for detected type)
- `size`, `sha256`, image `width`/`height`, and media `duration`
- `turn_id`, `message_id`, `download_status`, and `failure_reason`
- a sanitized `source_url` without query parameters or signed credentials

Artifact identity is based on `file-*`, `file_*`, or normalized
`file-service://` identifiers. Signed URLs are transient transport metadata,
not identity.

## File behavior

LogGPT Plus archives successfully fetched content byte-for-byte regardless of
type. This includes images (raster or vector), audio, video, PDFs, source/text
files, CSV/TSV, spreadsheets, documents, archives, and unknown binary data.
Unknown data receives a `.bin` extension.

Existing CSV, TSV, and spreadsheet files are ordinary artifacts. extract-chat
may render a small parseable tabular artifact as a table while preserving a
link to the original file. `--emit-tsv` creates a derived TSV only for an
embedded table without a matching downloaded table artifact.

## Compatibility

extract-chat accepts:

- version 2 `artifacts/` archives
- version 1 `artifact-manifest.json` archives
- legacy `<stem>/media/` and `media-manifest.json` bundles

When a manifest exists it is authoritative. Filename scanning is a fallback
for legacy packages only. ZIP extraction rejects absolute paths, traversal,
and symlinks.
