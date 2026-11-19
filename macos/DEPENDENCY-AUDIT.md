# macOS application qualification: first-gate checkpoint

Date: November 17, 2026. Status: **compatible packaging candidate and signed sandbox proof passed on the development Mac; UI review is next**. No application release is qualified by this checkpoint. The initial incompatible resolver result below is retained as evidence, not the current status.

November 18 update: the native product and GUI acceptance host now target macOS 14 by explicit product decision. The historical macOS 13 audit/probe baseline below is retained; the existing helper remains compatible with the newer app minimum. Raising the product minimum does not make the rejected macOS 15-only wheel suitable, nor does it replace actual macOS 14 and Intel runtime qualification.

## Reproducible evidence

The initial development environment used UnicodeFix 2.0.3 from a local wheel, not the project's pinned Git revision. A separate environment was therefore created under the ignored `build/macos-qualification/venv` directory. The normal project requirements, `mac-app` and `token-counting` extras, and pytest were installed there without changing the user's existing environment.

The resolver fetched UnicodeFix revision `9e1cca9f9bb20139c258fe17c68ae7ee33391337`, whose project version is 2.1.0. Its original LICENSE was inspected at that exact revision and is MIT. The installed distribution's `direct_url.json` records the same Git commit.

Run the inventory against this isolated environment:

```bash
build/macos-qualification/venv/bin/python scripts/audit_macos_dependencies.py --output build/macos-qualification/audit --minimum-macos 13.0
```

The command intentionally exits with status 2 when a candidate dependency fails qualification. It records package versions, runtime/build roles, original license texts and their hashes, project/source references, dependency declarations, and native file hashes/deployment requirements. Generated evidence remains ignored under `build/macos-qualification/audit/`:

- `dependency-inventory.json`: resolved candidate inventory and blocking findings.
- `THIRD-PARTY-NOTICES.txt`: candidate Python/runtime and package notice texts; not final distribution approval.
- `resolved-requirements.txt`: the exact installed versions and pinned UnicodeFix source; a snapshot, not a hash-locked release manifest.

## Initial resolver blocker

At the initial audit, the project targeted macOS 13.0 and UnicodeFix's allowed dependency range `tree-sitter-language-pack>=0.9.0` resolved to version 1.25.2. Its ARM64 `_native.abi3.so` contained:

```text
cmd LC_BUILD_VERSION
platform 1
minos 15.0
sdk 26.5
```

This is the library's deployment minimum, not its SDK or linked dylib version. Tests explicitly cover those distinctions. The wheel is also tagged `macosx_15_0_arm64`. That rejected candidate could not qualify for the agreed macOS 13 engine baseline unchanged. This was a dependency compatibility failure, not evidence that Python cannot run inside an App Store application. The corrected constraint and qualified development candidate are described below.

## License findings and remaining work

Every package in the resolved runtime/build closure carries packaged license or notice text. The inventory includes less obvious dependencies pulled in by UnicodeFix and token counting, rather than assuming only Extract Chat's direct dependencies ship. Examples include Pillow and its bundled component notices, the tree-sitter packages, Markdown formatters, and certifi under MPL-2.0. The PyInstaller notice includes its bootloader exception. The complete Python runtime notice is included.

These findings do not require publishing Extract Chat's own source merely because it uses those packages, but they are not a final compliance sign-off. Before release, identify the native libraries and data actually shipped by the frozen bundle, reconcile their notices and any source-availability obligations, document applicable license alternatives, and verify tokenizer-data redistribution and offline operation. Build-only tools and the full resolved dependency closure are not necessarily identical to the shipped bundle.

## Compatible candidate and sandbox proof

UnicodeFix itself has no declared macOS 15 requirement. The macOS-only packaging constraint in `macos/constraints.txt` selects tree-sitter-language-pack 0.9.1, within the pinned UnicodeFix revision's supported range. Its wheel bundles parsers locally and declares older macOS support. Its resolved tree-sitter dependency is 0.23.2. No UnicodeFix checkout, cross-platform requirement, application minimum OS, or conversion semantics were changed to accommodate the wheel. All 33 pinned UnicodeFix source/transform/Markdown tests passed with this candidate.

The frozen engine is now a console helper inside a correctly laid-out nested `ExtractChatEngine.app`, retaining Python while separating executable code, libraries, and resources. The original one-directory CLI layout failed deep app-bundle signing because metadata directories were interpreted as nested code bundles; the nested-app layout passes strict deep signature verification. GNU Readline and Tkinter are excluded because the conversion tool does not use interactive Python or Tk. The frozen-native audit attributes the 90 remaining libraries to wheel/runtime packages and found no deployment minimum above macOS 13. Tokenizer data for o200k_base and cl100k_base is bundled and a runtime hook rejects cache misses rather than downloading data.

The signed sandboxed Packaging Probe opened the real archive `2026-05-28-2026-08-18-artifact-test-for-loggpt+.zip` through Launch Services and accepted an output folder through NSOpenPanel. Its child inherited the app sandbox, had no network entitlement, and was given only `/usr/bin:/bin` in PATH, without developer Python or PYTHONPATH. It produced Markdown, HTML, token-limited continuity chunks, and 18 artifacts. Every saved artifact matched the original ZIP bytes. A subsequent Cancel operation interrupted the child without freezing the native UI. Transactional cleanup and remaining-queue cancellation are implemented and unit-tested separately in the new managed-job layer; the packaging probe itself is deliberately not the product job controller.

Evidence is under the ignored `build/macos-qualification/` directory: `audit-compatible/` contains the corrected dependency candidate; `audit-frozen/` contains actual native-library hashes, attribution, deployment minima, and runtime notices; `probe-results/` retains historical real-archive results. `scripts/build_macos_helper.sh` regenerates the candidate and frozen audits and includes their notice files. The obsolete packaging-only probe and its builder were retired after the actual product-view sandbox host superseded them; use `scripts/build_macos_gui_acceptance.sh` with the native tests under `macos/Tests/` for current GUI/CLI qualification.

This proves signed helper execution, document-open/file-picker access, local token counting, and output generation on the development Mac. It does not prove runtime behavior on the native app's macOS 14 minimum, Intel, a clean distribution installation, iCloud provider edge cases, or App Store acceptance. Retain these as release gates. Current private ChatGPT, refreshed Work, Dots and Hermes samples are preserved separately from Git; see [App Store preparation](APP-STORE-PREPARATION.md#validation-and-retained-evidence) for their location and the newer product-view/CLI qualification. The old packaging probe and its picker receipts do not qualify the new system-managed privacy-consent workflow.

## References

- [Pinned UnicodeFix license](https://github.com/unixwzrd/UnicodeFix/blob/9e1cca9f9bb20139c258fe17c68ae7ee33391337/LICENSE)
- [PyInstaller macOS packaging and sandbox limitations](https://www.pyinstaller.org/en/stable/usage.html)
- [PyInstaller licensing exception](https://pyinstaller.org/en/stable/license.html)
- [Apple: embedding a helper in a sandboxed app](https://developer.apple.com/documentation/xcode/embedding-a-helper-tool-in-a-sandboxed-app)
