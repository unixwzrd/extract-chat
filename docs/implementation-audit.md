# Archive enhancement implementation audit

## Implemented boundaries

- `archive.py` owns safe ZIP-based LGPT/legacy ZIP ingestion and rejects traversal and symlink members.
- `naming.py` owns canonical UTC `start-date-end-date-title` names.
- `chunking.py` owns deterministic Markdown continuity chunks, manifests, hashes, overlap, and the hard 524,288-byte final-file ceiling.
- `artifact_package.py` owns manifest v2/v1/legacy package discovery, safe local-path resolution, artifact placement, and lightweight table previews.
- `tables.py` owns HTML-table to TSV derivation when the archive does not already contain an equivalent table artifact.
- Source adapters normalize ChatGPT/Work, Dots and Hermes Desktop without inventing missing source content. Native activity grouping uses parent ancestry and exported identities without crossing user turns; call/result payloads remain inert.
- `TurnProcessorV2` builds the shared render document; Markdown and HTML share activity details, source-reference handling and artifact association.
- The CLI remains the orchestration layer and preserves legacy `--output` behavior while adding `--output-dir`, ZIP input, `both`, artifact directories, optional table derivation, and chunk controls.

## Redundancy and follow-up

The tracked formatter and CSS implementations have one authoritative import path. Ignored historical utility copies remain under `src/extract_chat/utils/`; current code does not import them, and package discovery explicitly excludes that deprecated package. Git ignore rules alone do not stop setuptools from finding local Python packages. Local copies are preserved, while built wheel/source archives must be checked to exclude them. `MANIFEST.in` explicitly includes documentation, native app/build sources and synthetic tests in source distributions while pruning generated/per-user native state and legacy utilities; this must not depend on an optional Git file-finder plugin or stale egg-info lists. Artifact package handling resides in its focused module. Existing Pydantic class-based configuration warnings are a separate Pydantic 3 migration item.

The native app uses one embedded engine for GUI and CLI. Obsolete packaging-only probes, the separate CLI companion build path and the automatic first-run folder-picker experiment are removed. Active regression harnesses under `macos/Tests/` remain. Generated runtimes/audits/caches, private exports and discarded artwork concepts stay outside the Git candidate; the selected icon master, original artwork provenance and release asset catalog are source assets.

## Next-release backlog: embedded apps, charts and activity metadata

Recorded November 19, 2026 after inspecting the supplied JSON fragment, screenshot and the retained refreshed ChatGPT Work fixture. This is investigation/backlog only; no parser, renderer or execution behavior has been changed. The sample's final assistant message contains three distinct unsupported representations, not just another media URL.

1. **Embedded HTML/JavaScript apps.** Recognize `metadata.content_references[]` entries with `type: client_defined_widget`, `category: app_block`, `name: visualize` and `data.widget_type: app_block`. The example has `language: html`, `entrypoint: index.html`, `bundle_version: 1`, `variant: inline`, a title/path and approximately 64 KB of embedded `data.content`. Its `matched_text` is a `visualize` marker containing the source path. The payload includes styles, SVG chart markup and scripts, including remote dependency references; it is not merely a downloadable file pointer. Preserve the complete source and provenance, show escaped source in a collapsed disclosure, and investigate a chart/app preview at the original transcript position. Decide static/offline fallback versus explicitly isolated active preview before implementation: never inject archived scripts into the trusted transcript or automatically fetch their dependencies. A workspace path is provenance, not authorization to open a local file.
2. **Structured chart widgets.** Separately recognize `client_defined_widget` entries with `category: visualization`, `data.widget_type: charts_widget_v2` and `language: recharts-json`. The example's `genui` marker corresponds to a bar chart whose metadata includes `chartType`, title/description, `xKey`, series, data, formatted data and axes/ticks. Plan a faithful HTML chart plus accessible tabular/text fallback, a collapsed chart-specification view, and a useful Markdown representation. Preserve placement/order alongside prose and the embedded app; do not silently discard either widget or confuse chart data with executable JavaScript.
3. **New tool-group metadata and exported code visibility.** Inspect `metadata.dil_v2_reasoning.appData` on associated `thoughts` messages. It contains a group title/count and ordered `items` with IDs, types, labels, activity state and icons; connector items can also expose `connectorId` and `toolName`. The sample includes `command_execution`, `file_change` and `connector_call` items, including a `library.create_library_file` call. Present these as grouped activity disclosures, correlate with actual calls/results when exported, and avoid duplicating summaries already shown elsewhere. The sibling `dil_v2_reasoning.code` value is a UI-rendering expression (`DIL.render(...)`), not the shell/Python command that performed the work.

The inspected final exchange contains six reported command executions, two reported file-edit items and one Library connector item, but no separate code/tool-result messages or command bodies/outputs for them. No analysis Python source was found in that exchange. Do not infer the language or reconstruct execution from labels. Show any actual exported Python, JavaScript, shell or other code and paired output when available; otherwise distinguish “reported execution; command/output not exported” from a renderer omission. Investigate the exporter/capture boundary if the browser has details absent from the JSON. Counts and file-change labels alone do not identify changed files or patch contents.

Acceptance work for that release: small synthetic fixtures for all three metadata forms, embedded source round-trip preservation, widget ordering and HTML/Markdown fallbacks, available-versus-missing code/output, call/result deduplication and inert-by-default rendering. Retain the real example privately; do not copy its sales data, full app source or screenshots into the public test suite. The existing private refreshed Work archive already contains both widgets and the tool-group metadata in its final exchange.

## Release gates

- Run the Python suite and the private corpus runner without modifying the corpus.
- LogGPT exporter changes are qualified in the sibling repository; its release or App Store submission does not qualify Extract Chat.
- Build both the Swift package and the native ExtractChatApp Xcode target.
- Produce and sign the self-contained helper before App Store archive validation.
- Complete Documents-exception review information, the applicable Feedback Assistant report, clean-distribution privacy consent/revocation checks, required-reason API/privacy-manifest review, architecture/OS qualification, and public support/privacy/terms pages. See [the submission checklist](../macos/APP-STORE-PREPARATION.md).
