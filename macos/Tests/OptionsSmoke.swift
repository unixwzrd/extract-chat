import AppKit

@main
struct OptionsSmoke {
    @MainActor static func main() throws {
        let cssDirectory = FileManager.default.temporaryDirectory.appendingPathComponent("ExtractChat-CSS-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: cssDirectory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: cssDirectory) }
        let bundledCSS = cssDirectory.appendingPathComponent("default.css")
        let customCSS = cssDirectory.appendingPathComponent("café.css")
        let defaultText = "pre { white-space: pre; overflow-x: auto; }\n"
        let customText = "/* 日本語 */\nbody { color: #123456; }\n"
        try defaultText.write(to: bundledCSS, atomically: true, encoding: .utf8)
        try customText.write(to: customCSS, atomically: true, encoding: .utf8)
        let defaultPreview = try StylesheetPreview.load(custom: nil, bundled: bundledCSS)
        precondition(defaultPreview.content == defaultText && defaultPreview.suggestedFilename == "extract-chat-default.css")
        let customPreview = try StylesheetPreview.load(custom: customCSS, bundled: bundledCSS)
        precondition(customPreview.content == customText && customPreview.source == customCSS && customPreview.suggestedFilename == "café.css")
        let savedCSS = cssDirectory.appendingPathComponent("saved.css")
        try customPreview.save(to: savedCSS)
        let savedText = try String(contentsOf: savedCSS, encoding: .utf8)
        let originalText = try String(contentsOf: customCSS, encoding: .utf8)
        precondition(savedText == customText && originalText == customText)
        do {
            _ = try StylesheetPreview.load(custom: cssDirectory.appendingPathComponent("missing.css"), bundled: bundledCSS)
            preconditionFailure("An unavailable selected stylesheet must not silently show the default")
        } catch { }

        let domain = "ai.unixwzrd.ExtractChat.OptionsTest.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: domain)!
        defer { defaults.removePersistentDomain(forName: domain) }
        let model = ExportModel(defaults: defaults)
        let permissions = ConversionPermissions(defaults: defaults)
        let home = ConversionPermissions.userHome!
        precondition(permissions.usesSystemFolderAccess(home.appendingPathComponent("Documents/Extract Chat/results")))
        precondition(permissions.usesSystemFolderAccess(home.appendingPathComponent("Downloads/archive.lgpt")))
        precondition(!permissions.usesSystemFolderAccess(home.appendingPathComponent("Documents-unrelated/result")))
        precondition(!permissions.usesSystemFolderAccess(home.appendingPathComponent("projects/result")))
        model.errorMessage = "Operation not permitted"
        precondition(model.hasAccessFailure)
        model.errorMessage = "Malformed conversation JSON"
        precondition(!model.hasAccessFailure)
        model.errorMessage = nil
        precondition(model.cancelButtonTitle == "Quit", "An empty queue has nothing to cancel")
        precondition(model.settings.format == "both" && !model.settings.chunks && model.settings.emitTSV)
        precondition(!model.closeOnSuccess, "Existing preferences without the new option must remain valid and default to staying open")
        precondition(!model.adjustTimeZone && !model.turnIndex)
        precondition(model.toolJSON == "readable")
        let lgptInput = URL(fileURLWithPath: "/tmp/LogGPT café.LGPT")
        model.addFiles([lgptInput, lgptInput])
        precondition(model.files.count == 1 && model.files[0].url == lgptInput)
        precondition(model.validation == nil && model.arguments(source: lgptInput, output: cssDirectory).contains(lgptInput.path))
        model.files = []
        let input = URL(fileURLWithPath: "/tmp/Extract Chat's café.zip")
        model.addFiles([input, input])
        precondition(model.files.count == 1)
        precondition(model.cancelButtonTitle == "Cancel", "Adding input prepares a new operation")
        precondition(model.validation == nil)
        precondition(!model.arguments(source: input, output: URL(fileURLWithPath: "/tmp/output")).contains("--chunk"))
        model.settings.chunks = true
        model.settings.maxBytes = "invalid"
        precondition(model.validation != nil)
        model.settings.format = "html"
        precondition(model.validation == nil && model.settings.chunks && !model.effectiveChunks)
        model.settings.format = "both"
        model.settings.maxBytes = "524288"
        model.settings.overlap = "none"
        let args = model.arguments(source: input, output: URL(fileURLWithPath: "/tmp/output"))
        precondition(args.contains("--chunk-overlap-turns") && args.contains("0"))
        model.closeOnSuccess = true
        model.adjustTimeZone = true
        model.timeZoneIdentifier = "America/Chicago"
        model.toolJSON = "raw"
        precondition(model.commands.contains("--tool-json raw"))
        model.turnIndex = true
        precondition(model.validation == nil)
        precondition(model.commands.contains("--timezone America/Chicago") && model.commands.contains("--turn-index"))
        model.timeZoneIdentifier = "invalid"
        precondition(model.validation != nil)
        model.adjustTimeZone = false
        precondition(model.validation == nil && !model.commands.contains("--timezone"))
        model.adjustTimeZone = true
        model.timeZoneIdentifier = "America/Chicago"
        precondition(ExportModel.validTimeZone("UTC+05:30") && !ExportModel.validTimeZone("UTC+24:00") && !ExportModel.validTimeZone("UTC-05:60"))
        precondition(model.saveSettings())
        let restored = ExportModel(defaults: defaults)
        precondition(restored.settings.chunks && restored.settings.overlap == "none")
        precondition(restored.closeOnSuccess)
        precondition(restored.adjustTimeZone && restored.turnIndex && restored.timeZoneIdentifier == "America/Chicago")
        precondition(restored.toolJSON == "raw")

        let savedSettings = model.settings
        let rowIDs = model.files.map(\.id)
        model.selection = Set(rowIDs)
        model.destination = URL(fileURLWithPath: "/tmp/custom-results")
        model.css = URL(fileURLWithPath: "/tmp/custom.css")
        model.settings.format = "html"
        model.settings.overwrite = true
        model.settings.mediaIndex = true
        model.settings.emitTSV = false
        model.settings.useCSS = true
        model.settings.verbose = true
        model.settings.schemaDetail = "full"
        model.settings.maxBytes = "1234"
        model.settings.maxLines = "50"
        model.settings.maxTokens = "1000"
        model.settings.encoding = "cl100k_base"
        model.settings.strategy = "paragraph"
        model.settings.overlap = "bytes"
        model.settings.overlapValue = "20"
        model.settings.uploadBatch = "3"
        model.resetToDefaults()
        precondition(model.settings == ExportSettings())
        precondition(!model.closeOnSuccess)
        precondition(!model.adjustTimeZone && !model.turnIndex)
        precondition(model.toolJSON == "readable")
        precondition(model.destination == nil && model.css == nil)
        precondition(model.files.map(\.id) == rowIDs && model.selection == Set(rowIDs))
        precondition(model.commands.contains("--format both") && model.commands.contains("--emit-tsv"))
        precondition(!model.commands.contains("--force") && !model.commands.contains("--chunk") && !model.commands.contains("--css-file"))
        precondition(ExportModel(defaults: defaults).settings == savedSettings, "Reset must not persist before OK")
        var idleQuitRequests = 0
        model.dismissConfiguration = { idleQuitRequests += 1 }
        model.cancel()
        precondition(idleQuitRequests == 0 && model.files.isEmpty && model.cancelButtonTitle == "Quit", "Pending Cancel discards setup, stays open, and offers Quit")
        precondition(model.settings == savedSettings, "Cancel must undo an unaccepted reset")
        precondition(model.closeOnSuccess, "Cancel must restore the previously accepted close option")
        precondition(model.adjustTimeZone && model.turnIndex && model.timeZoneIdentifier == "America/Chicago")
        precondition(model.toolJSON == "raw")
        model.addFiles([input])
        defaults.set("preserved", forKey: "unrelated-setting")
        defaults.set(["/not-an-authorized-test-path": Data([1, 2, 3])], forKey: "output-folder-access-v1")
        defaults.set(Data([0]), forKey: "destination-bookmark")
        defaults.set(Data([0]), forKey: "css-bookmark")
        let unavailable = ExportModel(defaults: defaults)
        unavailable.addFiles([input])
        precondition(unavailable.destinationNeedsSelection && unavailable.validation?.contains("saved destination") == true)
        unavailable.clearDestination()
        precondition(!unavailable.destinationNeedsSelection && unavailable.validation == nil)
        model.resetToDefaults()
        model.resetToDefaults() // Repeating reset is harmless and keeps the queue.
        precondition(model.saveSettings())
        precondition(ExportModel(defaults: defaults).settings == ExportSettings())
        precondition(!ExportModel(defaults: defaults).closeOnSuccess)
        precondition(model.files.count == 1)
        precondition(defaults.object(forKey: "destination-bookmark") == nil && defaults.object(forKey: "css-bookmark") == nil)
        precondition(defaults.string(forKey: "unrelated-setting") == "preserved")
        precondition((defaults.dictionary(forKey: "output-folder-access-v1")?["/not-an-authorized-test-path"] as? Data) == Data([1, 2, 3]), "Resetting conversion options must not discard remembered folder permissions")
        model.files = []
        precondition(model.cancelButtonTitle == "Quit")
        model.cancel()
        precondition(idleQuitRequests == 1, "The Quit action with an empty queue must request application exit")

        let tricky = "/tmp/a'b $(not-a-command); café.zip"
        let process = Process()
        let pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/sh")
        process.arguments = ["-c", "set -- " + ExportModel.quote(tricky) + "; printf '%s' \"$1\""]
        process.standardOutput = pipe
        try process.run()
        let output = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        precondition(process.terminationStatus == 0 && String(decoding: output, as: UTF8.self) == tricky)
        print("Swift option defaults, validation, reset/save/cancel, persistence, deduplication and shell quoting passed.")
    }
}
