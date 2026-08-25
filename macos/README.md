# Extract Chat for macOS

`ExtractChatApp` is the native SwiftUI front end for JSON and LogGPT+ ZIP archives. It exposes format, chunking, and TSV options without requiring Terminal use.

For development, it finds `extract-chat` in `/opt/homebrew/bin` or `/usr/local/bin`. A release/App Store archive must bundle a self-contained helper named `extract-chat` in the app Resources directory; the app does not download or execute Python from the network. The file importers provide sandbox-scoped access to the selected input and output directory.

Build the self-contained helper in a clean release environment with
`scripts/build_macos_helper.sh`, then add
`macos/ExtractChatApp/BundledHelper/extract-chat` to the app target's Copy
Bundle Resources phase. App Store signing/notarization must cover that nested
executable. The source tree intentionally does not commit a platform-specific
helper binary.

Open `macos/ExtractChatApp/ExtractChatApp.xcodeproj` for the sandboxed app target. The Swift package uses the same source for fast command-line validation:

```sh
swift build --package-path macos/ExtractChatApp
```
