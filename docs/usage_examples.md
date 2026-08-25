# extract-chat Usage Examples

- [extract-chat Usage Examples](#extract-chat-usage-examples)
  - [Most Common Cases](#most-common-cases)
    - [Convert One Conversation to Markdown](#convert-one-conversation-to-markdown)
    - [Convert One Conversation to HTML](#convert-one-conversation-to-html)
    - [Export One Assistant Turn as Jekyll Pages](#export-one-assistant-turn-as-jekyll-pages)
  - [Choosing the Right Format](#choosing-the-right-format)
  - [Working with LogGPT](#working-with-loggpt)
  - [Batch Validation](#batch-validation)
  - [Schema Drift and Diagnostics](#schema-drift-and-diagnostics)
  - [Media Inventory Only](#media-inventory-only)
  - [Development Workflow](#development-workflow)
  - [Related Docs](#related-docs)

This page is the practical companion to the CLI reference.

Use it when you want to answer questions like:

- Which format should I use?
- How do I export one specific answer?
- How do I process a LogGPT JSON file or LogGPT+ ZIP archive?
- How do I process a whole directory of JSON files?

For the full option reference, see [extract_chat.md](extract_chat.md).

## Most Common Cases

### Convert One Conversation to Markdown

```bash
extract-chat conversation.json --output conversation.md
```

Use this when you want a readable archive, notes file, or something easy to search in an editor.

### Convert One Conversation to HTML

```bash
extract-chat conversation.json --format html --output conversation.html
```

Use this when you want a browser-friendly output for review or sharing.

If you want your own stylesheet:

```bash
extract-chat conversation.json \
  --format html \
  --css-file site.css \
  --output conversation.html
```

### Export One Assistant Turn as Jekyll Pages

```bash
extract-chat conversation.json \
  --format jekyll \
  --jekyll-turn-id <assistant-turn-id> \
  --jekyll-base-slug my-article \
  --output out/jekyll \
  --force
```

Jekyll export is single-turn oriented.

That means:

- you choose one assistant turn with `--jekyll-turn-id`
- `extract-chat` breaks that turn into section pages
- a references page is generated alongside the section pages

If you want multiple assistant turns, run the command once per turn.

## Choosing the Right Format

- `markdown`: best for archives, note-taking, diffs, and local knowledge bases
- `html`: best for browser review and sharing
- `jekyll`: best for turning one long assistant response into publishable pages

If you want the whole conversation in one output, use Markdown or HTML.

If you want one substantial assistant answer turned into web pages, use Jekyll.

## Working with LogGPT

A common LogGPT workflow is:

1. Use LogGPT Basic to download a ChatGPT conversation as JSON, or use LogGPT Plus to download a ZIP containing the JSON and its artifacts.
2. Pass that `.json` or `.zip` file directly to `extract-chat`.
3. Keep the Markdown or HTML as an archive, or export a selected assistant turn to Jekyll.

```bash
extract-chat conversation.json --output-dir exported --format both
extract-chat conversation.zip --output-dir exported --format both
```

When the input is a LogGPT+ ZIP, `extract-chat` safely extracts the archive, locates its conversation JSON automatically, copies packaged artifacts into the output directory, and uses local artifact links in Markdown and HTML where possible.

For the archive layout, see [media-bundle-contract.md](media-bundle-contract.md).

## Batch Validation

If you have a directory of exported conversations and want to validate or render them in one run:

```bash
extract-chat \
  --batch-dir tmp/consolidated/JSON \
  --output tmp/batch-validate-run \
  --batch-formats both
```

This creates a run directory with:

- `markdown/`
- `html/`
- `reports/summary.md`
- `reports/results.csv`

Use batch mode when you are testing a mixed archive, checking for schema drift, or validating a large collection before publishing or ingesting it elsewhere.

## Schema Drift and Diagnostics

OpenAI export formats change over time. When `extract-chat` sees unfamiliar schema variants, it tries to keep going and records what it found.

Helpful options:

- `--schema-warning-detail full` to print the complete warning set
- `--gh-file-schema-issue` to prepare or file a GitHub issue for schema drift
- `--gh-repo` to override the default issue target repository

Example:

```bash
extract-chat conversation.json \
  --output out.md \
  --schema-warning-detail full \
  --gh-file-schema-issue
```

## Media Inventory Only

If you want to inspect known media references without downloading anything:

```bash
extract-chat conversation.json \
  --output out.md \
  --media-index
```

This writes a `media-index.json` file under a conversation-named subdirectory beside the output.

## Development Workflow

For local development:

```bash
git clone https://github.com/unixwzrd/extract-chat.git
cd extract-chat
pip install -e .
pytest -q
```

That gives you an editable install and runs the full test suite.

## Related Docs

- [Back to README](../README.md)
- [CLI Reference](extract_chat.md)
- [Python API](api.md)
- [Architecture Guide](extract_chat_architecture.md)
- [Media Bundle Contract](media-bundle-contract.md)
