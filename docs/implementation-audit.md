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

## Release gates

- Run the Python suite and the private corpus runner without modifying the corpus.
- LogGPT exporter changes are qualified in the sibling repository; its release or App Store submission does not qualify Extract Chat.
- Build both the Swift package and the native ExtractChatApp Xcode target.
- Produce and sign the self-contained helper before App Store archive validation.
- Complete Documents-exception review information, the applicable Feedback Assistant report, clean-distribution privacy consent/revocation checks, required-reason API/privacy-manifest review, architecture/OS qualification, and public support/privacy/terms pages. See [the submission checklist](../macos/APP-STORE-PREPARATION.md).
