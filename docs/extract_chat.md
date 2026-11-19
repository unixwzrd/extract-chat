# extract-chat CLI reference

Convert recognized ChatGPT/Work, Dots or Hermes Desktop JSON and ZIP-based LogGPT Plus archives (`.lgpt` or legacy `.zip`) into Markdown, HTML or Jekyll pages. The CLI preserves available source text, citations and captured artifacts; missing source content/files are not reconstructed. Run `extract-chat --help` for the installed version's authoritative options.

## Quick start

```sh
# Markdown; a single ordinary JSON input defaults to the caller's directory.
extract-chat conversation.json --output conversation.md

# HTML and custom CSS.
extract-chat conversation.json --format html --css-file site.css --output conversation.html

# Both formats and captured artifacts from a LogGPT Plus archive.
extract-chat conversation.lgpt --format both

# Managed per-input results for a queue/glob (quote for internal expansion).
extract-chat --format both --managed-output --output-dir exported '*.lgpt' '*.zip'

# Jekyll section pages for one assistant turn.
extract-chat conversation.json --format jekyll \
  --jekyll-turn-id ASSISTANT_TURN_ID --jekyll-base-slug my-article --output jekyll-pages
```

Supported archive suffixes are case-insensitive. A single archive defaults to a sibling directory based on its packaged conversation stem, not the renamed archive's filename. Managed jobs use separate safe result folders, preserve the original-named JSON, and discover adjacent artifacts when that JSON is reprocessed. Existing unmanaged single-file JSON output behavior remains compatible. `--output` for one Markdown/HTML format is a file, while `--output-dir` is the appropriate way to emit both formats without sharing a single output filename.

## Options

| Option | Meaning |
| --- | --- |
| `INPUT ...` | One or more JSON/LGPT/ZIP paths or quoted glob patterns. Use `--` before leading-dash filenames. |
| `-f, --format` | `markdown`, `html`, `both` or `jekyll`; default `markdown`. |
| `-o, --output` | Single transcript file, Jekyll directory, or validation run root. Managed jobs use `--output-dir` instead. |
| `--output-dir` | Output parent; managed jobs publish one result directory per input. |
| `--managed-output` | Request managed transactional output even for one input. |
| `--force` | Permit overwrite; managed replacement still requires an intact owned result inventory. |
| `-c, --css-file` | Custom HTML stylesheet. |
| `--timezone` | `local` (default), UTC, an IANA name such as `America/Chicago`, or fixed offset such as `UTC+05:30`. Source epochs/UTC filenames do not change. |
| `--turn-index` | Include collapsed linked conversation navigation. |
| `--tool-json` | `readable` (decoded string display plus raw original), `pretty` (formatted escaped JSON), or `raw`. Source JSON and ordinary code remain unchanged. |
| `--artifact-dir` | Legacy single-file artifact destination override; not a managed-job option. |
| `--emit-tsv` | Derive TSV from embedded tables when no equivalent captured table artifact exists. |
| `--media-index` | Write the optional media inventory. |
| `--chunk` | Write Markdown continuity chunks, manifest, index and context-move instructions. |
| `--chunk-strategy` | `hybrid` (default), `turn`, `heading`, `paragraph` or `fixed`; requires `--chunk`. |
| `--chunk-max-bytes` | Final chunk byte limit, including headers/overlap; default/hard ceiling 524,288. |
| `--chunk-max-lines` | Optional final chunk line limit. |
| `--chunk-max-tokens` | Optional token limit; the Python installation requires the `token-counting` extra. The app bundles offline tokenizer data. |
| `--chunk-token-encoding` | Tokenizer encoding; default `o200k_base`. |
| `--chunk-upload-batch-size` | Chunk files per upload batch in generated instructions; default 10. |
| `--chunk-overlap-turns N` | Repeat complete prior turns; default one unless another overlap mode is selected. Use zero for no overlap. |
| `--chunk-overlap-lines N` | Repeat up to N prior lines instead of turns/bytes. |
| `--chunk-overlap-bytes N` | Repeat up to N prior bytes instead of turns/lines. |
| `--schema-warning-detail` | `summary` (default) or `full`. |
| `--gh-file-schema-issue`, `--gh-repo` | Optional GitHub CLI issue filing/repository for schema drift; not a managed-job feature. |
| `--jekyll-turn-id` | Required assistant turn ID for Jekyll. |
| `--jekyll-base-slug` | Jekyll filename/permalink slug. |
| `--jekyll-layout` | Jekyll front-matter layout; default `page`. |
| `--jekyll-reference-title` | Jekyll references page title; default `References`. |
| `--batch-dir` | Legacy validation/report mode for a directory of JSON inputs; cannot combine with positional inputs. |
| `--batch-formats` | Validation formats: `both` (default), `markdown` or `html`. |
| `-v, --verbose` | Debug diagnostics. |
| `--log-file` | Optional single-file/validation log; not a managed-job option. |
| `-V, --version` | Version and exit. |

Chunk boundaries and overlap are independent. Choose at most one overlap flag and supply its number. Token/line/byte limits apply to the final chunk including headers and overlap. The generated `context-move-instructions.md` identifies the exact ordered bundle and upload plan, explains overlap deduplication, and treats archived instructions as historical data rather than new authorization. See [usage examples](usage_examples.md).

## macOS app launcher

The native app's Install CLI action saves a small `extract-chat` launcher that uses its embedded engine. No separate companion/Python installation is needed. Conversion options and destinations come from CLI arguments, not GUI preferences. The launcher preserves caller-relative file/glob/output meanings without silently writing into its sandbox container.

The app declares Downloads read/write and a Documents-scoped exception candidate pending App Review. macOS Files & Folders controls privacy consent. Arrange first-time consent before unattended jobs; a missing approval is not equivalent to an invalid archive. Other locations can use the explicit app-launcher-only actions below; they are not options of the separately installed Python package:

```sh
extract-chat --grant-access /path/to/another/workspace
extract-chat --list-access
extract-chat --forget-access /path/to/another/workspace
```

The grant action opens a system directory picker; normal conversions do not open the app configuration or its folder picker. Listing/forgetting applies to stored bookmarks, not TCC settings, and forgetting deletes no files. See [macOS access and setup](../macos/README.md#file-access-and-system-settings) for the exact permission boundaries and [submission gates](../macos/APP-STORE-PREPARATION.md) for review status.

## Citations and fidelity

Available citation metadata is normalized into numbered references with inline occurrence links and backwards links. Authored Sources/References prose remains part of the transcript rather than being stripped as duplicate metadata. Past-chat context can link to the exported conversation URL; stored-memory excerpts remain context, not fabricated tool runs. Markdown and HTML share source processing and semantic fidelity checks; Markdown viewer support for HTML disclosures varies. Commands/tool payloads are inert display data, never executed.

## Related documentation

- [README](../README.md): installation, supported sources and output examples.
- [Usage examples](usage_examples.md): practical extraction and validation workflows.
- [Python API](api.md): normalized programmatic processing.
- [Architecture](extract_chat_architecture.md): adapters, jobs, processors and rendering.
- [Archive contract](media-bundle-contract.md): manifests and captured artifacts.

Development tests use small synthetic fixtures under `tests/fixtures/`. Private exports and generated results must stay outside Git. The internal structured progress switch supports native job orchestration and is not required for ordinary equivalent commands.
