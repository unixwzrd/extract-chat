# extract-chat

![extract-chat](docs/images/extract-chat-banner.png)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](#) [![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Pydantic](https://img.shields.io/badge/Pydantic-2.0%2B-red)](#) [![UnicodeFix](https://img.shields.io/badge/UnicodeFix-Integrated-orange)](#)

- [extract-chat](#extract-chat)
  - [Works with LogGPT](#works-with-loggpt)
  - [Where this fits (AI / ML workflows)](#where-this-fits-ai--ml-workflows)
  - [Typical Use Cases](#typical-use-cases)
  - [What It Produces](#what-it-produces)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Documentation](#documentation)
  - [Python API](#python-api)
  - [Known Gaps](#known-gaps)
  - [Development](#development)
  - [Support](#support)
  - [Contributing](#contributing)
  - [Support This and Other Projects](#support-this-and-other-projects)
  - [Copyright](#copyright)
  - [Changelog](#changelog)
  - [License](#license)


`extract-chat` converts ChatGPT/Work, LogGPT Dots, and Hermes Desktop conversation JSON or compatible ZIP-based archives (`.lgpt` and legacy `.zip`) into readable Markdown or HTML conversation logs, with preserved citation links, local artifacts, schema diagnostics, and collapsible tool activity.

Version 1.0.0 introduces the first native macOS application, requiring macOS 14 or later. The app and Python engine share this version, with source and support documentation identified by the `v1.0.0` GitHub tag. The GUI includes a product icon, Reset to Defaults, and batch extraction through its bundled engine, with progress, cancellation and visible error/result handling. The native build has been uploaded to App Store Connect; the GitHub source tag does not establish App Store approval or availability. See the [release checklist](macos/APP-STORE-PREPARATION.md) for remaining qualification and known runtime-symbol warnings.

The initial native macOS release is Apple Silicon-only (`arm64`). Intel/universal support is deferred until a matching engine and its native dependencies are qualified; the app's macOS minimum remains 14.

Dots support accepts LogGPT's `loggpt.dots` version 1 JSON or ZIP using the same CLI options, including `--format both --chunk`. A dedicated adapter resolves human/Dot authorship from room membership and produces a chronological transcript. Linked task and nested reply histories are not included; their references remain in the source JSON. Packaged direct attachments link to local files. Existing ChatGPT and ChatGPT Work inputs retain their normalization and schema diagnostics.

Hermes Desktop support recognizes the desktop export envelope (`exported_at`, `session_id`, `message_count`, `messages`) and validates message identities, roles, timestamps, session membership and tool calls through a separate source adapter. It retains original messages even when marked compacted/inactive, without repeating compression summaries as user prompts. Original summary records and native metadata remain in the source JSON and normalized provenance; summary-only exports are explicitly labeled, not claimed to be full histories. Thoughts and paired tool-call arguments/results are individually collapsed in HTML and in Markdown viewers supporting `<details>`. Commands and results are inert text, never replayed. A raw export does not contain the files merely mentioned in its tool output, and no referenced local path is automatically opened or copied. The same format, continuity, batch and native-GUI workflows apply; Hermes CLI JSONL and other unverified Hermes formats are not included in this adapter.

Tool arguments/results containing valid JSON objects or arrays have a JSON-shaped readable display plus a collapsed Raw JSON view. The readable display keeps braces, brackets, quoted keys/values, indentation and commas between key/value pairs, but decodes string escapes exactly once: encoded newlines become real line breaks and quoted commands become readable, while a literal backslash-n, shell escape or Windows path remains literal after decoding. It is a human-readable representation, not necessarily valid machine JSON; the original stays in Raw JSON and the retained original-named source file. Consecutive numbered file lines use a right-aligned `number | text` gutter with padding after the separator, retaining code indentation. Thoughts, prose and non-JSON code are not globally unescaped. Malformed, duplicate-key or excessively structured payloads keep their original view instead of being guessed at. This presentation is shared by Hermes and the existing ChatGPT/Work tool sections; their source-specific grouping remains unchanged.

If you've ever downloaded your ChatGPT history and opened it thinking:

> “What am I supposed to do with this?”

This tool fixes that.

It converts raw exports into:

- 📄 readable Markdown (notes, archives, documentation)
- 🌐 clean HTML (browse or share)
- 🧱 structured content (Jekyll pages)
- 🧠 AI-ready data (for embeddings, RAG, and agents)

And it preserves things most tools lose:

- references and citations  
- tool calls and hidden assistant activity  
- system prompts and reusable context  

## Works with LogGPT

[`LogGPT`](https://github.com/unixwzrd/LogGPT) (also on the [Mac App Store](https://apps.apple.com/us/app/loggpt/id6743342693?mt=12)) downloads your ChatGPT conversations as JSON.

`extract-chat` is the next step.

**Typical workflow:**

1. Use LogGPT to download your conversation
2. Run `extract-chat` on the JSON or LogGPT Plus archive (`.lgpt` or legacy `.zip`)
3. Get a clean, readable, portable transcript

New LogGPT Plus artifact bundles use `.lgpt`, a standard ZIP container with the original conversation JSON, artifacts and manifest. Standalone JSON downloads remain `.json`. Extract Chat for macOS registers `.lgpt` with the Finder description **LogGPT Plus file for Extract Chat**; double-click opens the archive in the configuration queue, and OK starts extraction. Extract Chat is also an Open With choice for JSON and legacy ZIPs without replacing their existing default apps. Add Files, Finder opening, drops and the CLI all accept `.lgpt`; existing `.zip` archives remain supported and are not renamed. The extension does not bypass archive safety or source validation.

With **LogGPT Plus**, you can also download all media (images, audio, files), and `extract-chat` will automatically link that media into the output. Version 0.7.0 adds support for generated files and uploaded attachments captured from ChatGPT Work conversations.

Together, they form a complete local archive + processing pipeline for ChatGPT data.

## Where this fits (AI / ML workflows)

This is not just a formatter—it’s a bridge between ChatGPT and real systems.

You can use `extract-chat` with:

- local RAG pipelines  
- vector databases  
- agent frameworks (OpenClaw, Hermes, custom agents)  
- research and forensic workflows  

It enables:

- conversation chunking for embeddings  
- replayable context for agents  
- structured memory ingestion  
- cross-session continuity  

Think of it as:

> **ChatGPT → structured data → usable intelligence**

## Typical Use Cases

- 📚 Archive ChatGPT conversations into readable documents  
- 🧠 Feed conversations into embeddings / vector databases  
- ✍️ Publish long-form content (Jekyll, blogs, docs)  
- 🔍 Preserve references, citations, and tool activity for analysis  
- 🔁 Reuse prior conversations for continuity  
- ⚖️ Maintain structured logs for research or forensic workflows  

## What It Produces

- A normal user/assistant conversation transcript.
- A separate `System Context` section when the export contains reusable profile or instruction context.
- A byte-for-byte copy of the original JSON, **with its original filename**, at the top of every completed native-app or managed CLI result folder (`--managed-output`, multi-file jobs, or `--progress-json`). ZIP inputs retain their selected conversation JSON filename; direct JSON inputs retain their input filename. The copy includes all exported metadata and branches, so sharing the entire result folder also shares that source. Legacy single-file non-managed output and validation/Jekyll workflows are unchanged.
- A per-assistant-turn Activity disclosure with independently expandable reasoning, progress updates and paired tool commands/results. It includes records present in the export even when the source interface does not display them, with timestamps, status, model and relevant exported fields. Calls/results are paired from native ancestry and tool names or explicit call IDs, never timestamp proximity alone. Missing counterparts and activity without a visible assistant reply are explicitly retained, not silently discarded.
- Assistant model slugs on each reply and on activity records, so model changes remain visible. Exported reasoning summaries/chunks are displayed as text rather than Python object representations; empty reasoning records explicitly state that no text was exported.
- A separate Context used disclosure for memory/past-conversation citations, preserving their titles, excerpts and reasons with safe absolute ChatGPT links. These attribution records are not mislabelled as media or invented tool invocations.
- Activity identity uses labelled Author / Time / Model / Tool / Channel / Message status / Turn ID fields rather than a joined status line. Grouped `commentary` messages are labelled Assistant commentary, distinct from exported reasoning. Turn ID here is the original mapping/message node ID; native exchange-level IDs remain under Exported fields.
- Returned image-generation prompts, dimensions and available generation parameters appear as readable text with the tool result and captured image. Prompt provenance is labelled (for example, returned `metadata.dalle.prompt`); the prompt is associated with a local artifact by its exact file identifier, not a filename/title guess. It is not substituted into empty call arguments, executed, fetched from the network, or used to infer an unexported image-model version.
- Explicit patch/diff/file-detail fields are displayed when exported. A work summary containing only a count is labelled as such; a bare `apply_patch` command without a patch body is not presented as a recovered diff or evidence of which files were created, modified or deleted.
- A per-assistant-turn `References` collapsible section with forward and backward citation links.
- Inline source markers at their exported positions, including modern ChatGPT citation widgets, with the reference list retained below the answer.
- Separate role, turn ID and timestamp lines, with local timezone and UTC offset shown by default. Use `--timezone UTC`, `--timezone America/Chicago`, or `--timezone UTC+05:30` for display-only conversion; source timestamps and filenames are unchanged. Named zones use installed IANA timezone data; unavailable names fail explicitly.
- Optional collapsed Time / Role / Contents navigation using `--turn-index`. Related assistant progress updates are retained under the main response when native exchange IDs and parent links confirm the relationship; separate branches are not merged.
- Optional Jekyll page export for long assistant turns and reference bundles.

Native-app and managed CLI outputs use one result folder:

```text
result-folder/
  original-conversation-filename.json
  conversation.md / conversation.html
  artifacts/                     # only when artifacts or derived tables exist
  artifact-manifest.json          # when provided by the source package
  media-index.json               # only when requested and media is present
  conversation-chunks/           # only when chunking is requested
  .extract-chat-result.json       # safe-overwrite inventory, not transcript data
```

Re-run the retained named JSON with different options to regenerate the transcript. Artifact discovery checks adjacent `artifacts/` or legacy `media/` plus their manifests first, then the older `<JSON-stem>/` package layout. Only artifacts and package manifests are copied; previous renders, inventories, chunks and unrelated sibling files are not copied into a new result. Existing manifest paths are adjusted for the new result location without changing original JSON or artifact bytes. No normalized conversation JSON or JSON-mode comparison directories are required. Empty derived-table directories are not created.

The macOS app exposes **Include conversation index** and **Use a specific time zone** in Output. Both are off initially; without an override, timestamps use this Mac’s local zone, including the offset appropriate to each date. These options apply to Markdown/HTML; continuity chunks use the same display timezone. Context is rendered only when profile/instruction fields actually exist in the export. A missing context section does not imply that private account settings were recovered.

**Advanced options → Tool JSON** controls valid JSON tool arguments/results: **Readable JSON + Raw JSON** (default) keeps the JSON structure while decoding string values for human display, and keeps the original collapsed; **Formatted JSON (escaped)** adds indentation while retaining JSON string escapes; **Original JSON (escaped)** shows the payload's original layout and escapes. The CLI equivalents are `--tool-json readable`, `--tool-json pretty`, and `--tool-json raw`; continuity chunks use the same choice. Thoughts, ordinary code and source files are not rewritten. Invalid/nonstandard JSON retains its fallback view.

In readable mode, unnecessary double-quote escapes in native tool commands' quoted `JSON` heredoc bodies are removed directly in the displayed command. Existing whitespace, line breaks, other backslashes and the surrounding command are retained; there is no additional view or reformatting. Already-valid JSON and required nested quote escapes are preserved. Source JSON, formatted/raw modes and ordinary Python/shell code remain unchanged, and recorded commands are never executed.

The default HTML stylesheet keeps code/tool output lines intact and scrolls long lines horizontally, without wrapping at dashes or altering the text. In the native app, **Advanced options → View CSS…** opens the current stylesheet in a read-only dialog: the built-in default when custom styling is off, or the selected custom file when it is on. **Copy** copies the complete CSS; **Save As…** saves a UTF-8 copy without changing the stylesheet selection. Edit that copy in your preferred editor, then select it with **Choose CSS…**. The bundled default is generated from the conversion engine's stylesheet during packaging, not maintained as a second independent theme.

HTML uses compact paragraph spacing while preserving code whitespace and within-paragraph line breaks. Each answer's References is followed by Artifacts (file/image/media pointers) and Related links (additional web URLs). URLs already cited in References are not repeated under Related links. Rendered HTTP(S) links omit `utm_source` while preserving other query values and fragments; code/tool payloads and original archive/JSON bytes remain unchanged.

Only captured sandbox files become local download links. If a file is absent or its manifest records a failed download, the transcript labels it “not captured,” preserves the locator and failure reason as text under Artifacts, and reports an `unavailable_artifact` warning. It does not leave a clickable session-only `sandbox:` URL, fetch missing files, or reconstruct their contents. Link resolution respects fenced/inline code and handles encoded filenames. Calls with matched results advertise the result count and use a Result / output heading; result records without exported calls remain visible separately. Citation publication dates accept epoch timestamps as well as conventional dates rather than misreading timestamp prefixes as years.

Stored-memory citations are plain text: the exported personalization/settings URL does not identify a particular memory. Past-chat citations retain their real conversation links. In standalone HTML, outgoing links and captured image previews open in a new tab with `noopener noreferrer`; same-page index/citation anchors stay in the current transcript, preserving disclosure state. Captured images use the local artifact copy, and the image itself is clickable. Explicit download links retain their download behavior. Standard Markdown link navigation remains controlled by the viewer.

The optional conversation index uses smaller, single-line rows, compact date/time/zone labels and excerpts shortened to at most 80 characters with `...` when truncated. The Time column takes 25% of the table, Role retains 12%, and Contents uses the remaining space. HTML additionally uses width-aware ellipsis; timestamp tooltips retain milliseconds and the UTC offset, and excerpt tooltips provide a longer preview. Full timestamps and conversation text remain unchanged in the transcript.

HTML rendering follows CommonMark, with tables enabled: lists immediately following prose are recognized without requiring an extra blank line, including nested bullets and ordered lists. Markdown output preserves the authored Markdown rather than inserting global blank-line or escape replacements. HTML from transcript text is displayed inertly, except the generated citation anchors; code fences remain code. The renderer is `markdown-it-py`, already used by UnicodeFix and now declared as a direct dependency. Transcript metadata labels the selected tool-JSON mode, avoiding confusion between decoded readable fields and escaped formatted/original JSON.

## Installation

Requires Python 3.11+. UnicodeFix is pinned to a tested Git revision so upstream changes do not silently change the installed dependency.

If you just want to use the tool, the easiest option is to install it directly from GitHub:

```bash
pip install "git+https://github.com/unixwzrd/extract-chat.git"
```

If you want a specific release:

```bash
pip install "git+https://github.com/unixwzrd/extract-chat.git@v1.0.0"
```

If you prefer to clone the repository first:

```bash
git clone https://github.com/unixwzrd/extract-chat.git
cd extract-chat
pip install .
```

For development, clone the repository and install in editable mode:

```bash
git clone https://github.com/unixwzrd/extract-chat.git
cd extract-chat
pip install -e .
```

After an editable install, run the test suite before opening a pull request or publishing changes:

```bash
pytest -q
```

`tests/test_formatter_parity.py` renders Markdown as CommonMark with tables and HTML disclosures, then compares it with standalone HTML. The visible-turn acceptance check requires matching role/order, text and semantic formatting: headings, emphasis, nested/ordered lists, quotes, inline/fenced code, tables, line breaks and links. It ignores separately collapsed reasoning/tool activity, so a continuation transcript need not reproduce that noise. Additional formatter regression checks cover ordered turn/citation anchors, disclosure order, code/tool payloads, destinations and activity identity/time/model fields. Synthetic ChatGPT, Work, Dots and Hermes cases run offline in the regular suite; deliberate-damage tests verify that missing text/formatting or reordered turns are detected. This checks semantic fidelity, not identical CSS or every Markdown viewer's layout.

To audit private sample extracts without committing their contents, point the optional check at a directory containing per-conversation folders with matching `.md` and `.html` transcripts:

```bash
EXTRACT_CHAT_REVIEW_DIR=/absolute/path/to/review-root pytest -q tests/test_formatter_parity.py
```

The native app declares Downloads read/write access and a Documents-scoped exception candidate pending App Review, with consent managed by macOS Files & Folders. It does not impose a custom startup folder-selection dialog. Its command group has Install CLI for saving a small `extract-chat` launcher on your PATH, using the same app's embedded engine without its GUI configuration or saved conversion options. Keep the app at its installed location; updating it in place updates the CLI too. No separate companion or Python installation is needed. Use `--output`/`--output-dir` to choose results, for example under `~/Documents/Extract Chat`; Beside each input remains the GUI default. Paths/globs retain their caller-directory meaning without demanding directory-list access merely to launch a command. First-time system privacy approval should be completed interactively before background jobs. File > Authorize Working Folders… and `extract-chat --grant-access` remain explicit fallbacks for other locations, not requirements for Downloads/Documents. See [app-installed command line](macos/README.md#app-installed-command-line) for permission recovery, exception review and qualification limits; the management switches belong to the app launcher, not the separately installed Python package.

Notes:

- Most people will use the command-line tool `extract-chat`.
- The Python package name is `extract_chat` if you do want to import it from code.
- The CLI entry point is `extract-chat`.
- Standalone HTML rendering uses CommonMark with table support through `markdown-it-py`.
- Unicode normalization uses [`UnicodeFix`](https://github.com/unixwzrd/UnicodeFix), currently installed from GitHub.

## Quick Start

Multiple conversations:

```bash
extract-chat --format both --chunk --output-dir converted first.zip second.json
extract-chat --format both --output-dir converted 'archives/*.zip'
```

Shell-expanded filenames and quoted glob patterns are accepted; existing literal filenames take precedence over wildcard interpretation. Matches are sorted per pattern and duplicate resolved files are removed. Use `**` explicitly for recursive patterns, or `--` before leading-dash input names. Unmatched patterns, directories, and unsupported file types fail preflight without producing outputs.

Multiple inputs create a separate result folder per input under `--output-dir`, or beside each source if no destination is given. Existing results get numbered folders by default. In this managed mode, `--force` replaces only recognized Extract Chat result folders without additional user files; it never replaces an arbitrary directory. Each conversion is staged and published after success, and one failed input does not discard other completed conversions. `--output` and `--artifact-dir` remain single-file options. The existing `--batch-dir` workflow is separate validation tooling and cannot be combined with positional inputs.

`--managed-output` explicitly selects managed result folders for a single input too; it is included in the GUI's equivalent command so copied workflows retain the same output/collision behavior. `--progress-json` additionally emits versioned, newline-delimited job/progress events on stdout and retains diagnostic logs on stderr. Interrupted managed jobs exit with status 130, failed batches with status 1, and successful batches with status 0. The native [macOS application](macos/README.md) opens with an empty queue; use Add Files, configure the batch, and select OK to extract. The default creates a result folder beside each source archive, requesting parent-folder permission only when needed by the sandbox.

Markdown:

```bash
extract-chat path/to/conversation.json -o out.md
```

HTML:

```bash
extract-chat path/to/conversation.json --format html --output out.html
```

Complete archive extraction with UTC `start-date-end-date-title` names:

```bash
extract-chat conversation.zip \
  --format both \
  --emit-tsv \
  --chunk
```

Pass either a standalone conversation JSON file or a LogGPT+ ZIP as the positional input. Without `--output-dir`, a ZIP creates a sibling directory matching the conversation stem packaged inside it so exports sort with their source archives even if the ZIP was renamed. Generated transcript, chunk, and artifact-package names use the UTC start and update dates, for example `2026-08-15-2026-09-09-this-is-the-title-of-the-chat`. Use `--output-dir` to choose a different destination. Downloaded artifacts are copied to `<destination>/<generated-stem>/artifacts/`, and Markdown/HTML links prefer those local files. Existing CSV, TSV, and spreadsheet files remain ordinary original artifacts. Small parseable CSV/TSV artifacts may also be displayed as tables while the original download link is retained. `--emit-tsv` only derives a TSV from an embedded table when no matching downloaded table artifact is present.

Local artifact links remain beside the rendered output even when the input and output share a filename stem. ZIP extraction recovers older unflagged UTF-8 filenames only when confirmed by the artifact manifest. Files whose paths differ only by letter case receive distinct derived filenames such as `REPORT--2.xlsx`, preserving both on case-insensitive filesystems. Derived manifests follow renamed package and artifact paths, retaining the original path in `archive_relative_path`; source ZIPs and JSON files are not modified.

Continuity chunks default to hybrid boundary selection with one turn of overlap. Every final Markdown part is measured after headers and overlap are added and may never exceed 524,288 UTF-8 bytes. Boundary strategy and overlap mode are independent; use `--chunk-strategy`, the byte/line/token limits, and at most one of the turn/line/byte overlap flags to select the behavior you need.

Every chunk directory includes `context-move-instructions.md`, generated from the actual bundle metadata. It records the chunk count, ordered filenames, boundary strategy, overlap mode, size ceiling, and upload batches so the transcript can be transferred into a fresh model context without editing a hand-written prompt. The upload plan defaults to 10 conversation chunks per batch and can be changed with `--chunk-upload-batch-size FILES`.

The native macOS front end lives in `macos/ExtractChatApp`; see
`macos/README.md` for development and helper-bundling details.

Jekyll bundle:

```bash
extract-chat path/to/conversation.json \
  --format jekyll \
  --jekyll-turn-id <assistant-turn-id> \
  --jekyll-base-slug my-conversation \
  --output tmp/jekyll-pages \
  --force
```

Batch validation run:

```bash
extract-chat \
  --batch-dir tmp/consolidated/JSON \
  --output tmp/batch-validate-run \
  --batch-formats both
```

## Documentation

The README stays intentionally high-level. Use the docs below for detail:

- [docs/extract_chat.md](docs/extract_chat.md) for command-line reference and option details
- [docs/usage_examples.md](docs/usage_examples.md) for examples, workflows, and common use cases
- [docs/api.md](docs/api.md) for Python/library usage
- [docs/extract_chat_architecture.md](docs/extract_chat_architecture.md) for internal pipeline details
- [docs/media-bundle-contract.md](docs/media-bundle-contract.md) for local media bundle integration

## Python API

`extract-chat` can also be used from Python, but the CLI is still the primary public interface.

If you want programmatic usage, see:

- [docs/api.md](docs/api.md) for loading JSON, building a render document, rendering Markdown/HTML, and exporting Jekyll pages
- [docs/extract_chat_architecture.md](docs/extract_chat_architecture.md) for internal pipeline details

The short version is:

- load with `Conversation`
- process with `TurnProcessorV2`
- render with `MarkdownFormatter` or `HTMLFormatter`
- use `JekyllTurnExporter` if you want one assistant turn exported as Jekyll pages

## Known Gaps

- The native build 1 upload reports missing runtime dSYMs for the embedded engine/dependencies; the main Swift app's symbols are present. This reduces crash-diagnostic detail inside those components and remains a [packaging follow-up](macos/APP-STORE-PREPARATION.md#runtime-debug-symbol-limitation).
- Next release: recognize embedded HTML/JavaScript app blocks, structured chart widgets and newer tool-group metadata in ChatGPT Work exports. Preserve/show exported source and code/output without fabricating execution details missing from the JSON; preview safety and offline fallbacks remain to be designed. See the [investigated backlog](docs/implementation-audit.md#next-release-backlog-embedded-apps-charts-and-activity-metadata).
- Authenticated media downloading still belongs to `LogGPT Plus`, not `extract-chat`.
- The native ExtractChatApp still requires a separately built, signed helper for App Store distribution.
- Spreadsheet formats that require a workbook parser are linked as original artifacts rather than rendered inline.
- The test suite still emits Pydantic v2 deprecation warnings from older schema modules that have not been migrated to `ConfigDict` yet.

## Development

Common development workflow:

```bash
git clone https://github.com/unixwzrd/extract-chat.git
cd extract-chat
pip install -e .
pytest -q
```

Run tests manually with:

```bash
pytest -q
```

There is also a minimal GitHub Actions workflow that runs tests and a packaging smoke test on pushes and pull requests.

The tests cover:

- traversal and transcript shaping
- citation grouping and numbering
- Markdown/HTML reference parity
- CLI execution
- Jekyll export wiring

For the fuller command reference and deeper examples, use:

- [docs/extract_chat.md](docs/extract_chat.md)
- [docs/usage_examples.md](docs/usage_examples.md)

## Support

For version 1.0.0, use the [tagged source and documentation](https://github.com/unixwzrd/extract-chat/tree/v1.0.0) and [changelog](CHANGELOG.md). Report bugs through [GitHub Issues](https://github.com/unixwzrd/extract-chat/issues), including the app/CLI version, macOS or other host OS version, input source (ChatGPT/Work, Dots or Hermes), file type, selected options and sanitized error text. Prefer a small synthetic reproducer. Do not post private conversation exports, credentials, signed download URLs or personal filesystem paths in public issues. The [product support page](https://unixwzrd.ai/projects/extract-chat/) is the native app's stable support entry point.

## Contributing

Issues and pull requests are welcome.

If you are contributing code:

```bash
git clone https://github.com/unixwzrd/extract-chat.git
cd extract-chat
pip install -e .
pytest -q
```

Please keep committed fixtures synthetic or redacted, and include tests when you change processor, formatter, or CLI behavior.

## Support This and Other Projects

If UnicodeFix (or my other projects) saved your bacon or made you smile, please consider fueling my caffeine habit and indie dev obsession...

- [Patreon](https://patreon.com/unixwzrd)
- [Ko-Fi](https://ko-fi.com/unixwzrd)
- [Buy Me a Coffee](https://buymeacoffee.com/unixwzrd)

Quite a bit of effort goes into preparing these releases. *One coffee = one more tool released to the wild...*🤔

Thank you for keeping solo development alive!

## Copyright

Copyright 2026  
[unixwzrd@unixwzrd.ai](mailto:unixwzrd@unixwzrd.ai)

## Changelog

**See [CHANGELOG.md](CHANGELOG.md) for the latest drop.**

## License

[MIT License](LICENSE)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
