# Archive enhancement implementation audit

## Implemented boundaries

- `archive.py` owns safe LogGPT+ ZIP ingestion and rejects traversal and symlink members.
- `naming.py` owns canonical UTC `start--end--title` names.
- `chunking.py` owns deterministic Markdown continuity chunks, manifests, hashes, overlap, and the hard 524,288-byte final-file ceiling.
- `artifact_package.py` owns manifest v2/v1/legacy package discovery, safe local-path resolution, artifact placement, and lightweight table previews.
- `tables.py` owns HTML-table to TSV derivation when the archive does not already contain an equivalent table artifact.
- `TurnProcessorV2` associates tool-produced artifact pointers with the next visible assistant turn.
- The CLI remains the orchestration layer and preserves legacy `--output` behavior while adding `--output-dir`, ZIP input, `both`, artifact directories, optional table derivation, and chunk controls.

## Redundancy and follow-up

The tracked formatter and CSS implementations have one authoritative import path. Two ignored historical copies remain under `src/extract_chat/utils/`; they are not imported or packaged and were left untouched because they are untracked user files. Artifact package handling was removed from `cli.py` into its own focused module. Existing Pydantic class-based configuration warnings are a separate Pydantic 3 migration item.

## Release gates

- Run the Python suite and the private corpus runner without modifying the corpus.
- Validate both LogGPT Xcode schemes and inspect the embedded `manifest.json` product name.
- Run `node tests/loggpt-export.test.js`.
- Build both the Swift package and the native ExtractChatApp Xcode target.
- Produce and sign the self-contained helper before App Store archive validation.
