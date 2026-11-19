import AppKit
import Combine
import UniformTypeIdentifiers

struct ExportSettings: Codable, Equatable {
    var format = "both"
    var chunks = false
    var emitTSV = true
    var mediaIndex = false
    var overwrite = false
    var strategy = "hybrid"
    var maxBytes = "524288"
    var maxLines = ""
    var maxTokens = ""
    var encoding = "o200k_base"
    var overlap = "turns"
    var overlapValue = "1"
    var uploadBatch = "10"
    var verbose = false
    var schemaDetail = "summary"
    var useCSS = false
}

struct InputRow: Identifiable {
    let id = UUID()
    let url: URL
    var status = "Ready"
    var progress: Double? = nil
    var active = false
    var output: URL?
    var error: String?
}

struct StylesheetPreview: Identifiable {
    let id = UUID()
    let title: String
    let source: URL
    let content: String
    let suggestedFilename: String

    static func load(custom: URL?, bundled: URL) throws -> StylesheetPreview {
        let source = custom ?? bundled
        let scoped = source.startAccessingSecurityScopedResource()
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        let content = try String(contentsOf: source, encoding: .utf8)
        return StylesheetPreview(title: custom == nil ? "Default HTML stylesheet" : "Custom HTML stylesheet", source: source, content: content, suggestedFilename: custom?.lastPathComponent ?? "extract-chat-default.css")
    }

    func save(to url: URL) throws {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        try content.write(to: url, atomically: true, encoding: .utf8)
    }
}

@MainActor
final class ExportModel: ObservableObject {
    @Published var files: [InputRow] = [] {
        didSet {
            if !isRunning && oldValue.map(\.id) != files.map(\.id) { batchFinished = false }
        }
    }
    @Published var selection: Set<UUID> = []
    @Published var settings = ExportSettings()
    @Published var destination: URL?
    @Published var destinationNeedsSelection = false
    @Published var css: URL?
    @Published var stylesheetPreview: StylesheetPreview?
    @Published var cliInstallationMessage: String?
    @Published var status = "Add JSON, LGPT or ZIP files, choose your options, then select OK to extract."
    @Published var isRunning = false
    @Published var isCancelling = false
    @Published var diagnostics = ""
    @Published var errorMessage: String?
    @Published var showDetails = false
    @Published var closeOnSuccess = false
    @Published var adjustTimeZone = false
    @Published var timeZoneIdentifier = TimeZone.current.identifier
    @Published var turnIndex = false
    @Published var toolJSON = "readable"
    @Published private var batchFinished = false
    var closeAfterSuccessfulExport: (() -> Void)?
    var conversionDidFinish: (() -> Void)?
    var showConfiguration: (() -> Void)?
    var dismissConfiguration: (() -> Void)?
    var resizeConfiguration: ((CGFloat) -> Void)?
    private let defaults: UserDefaults
    private let runner: ConversionRunner
    private let permissions: ConversionPermissions
    private var inputIndices: [String: Int] = [:]
    private var cancellationAcknowledged = false

    init(defaults: UserDefaults = .standard, runner: ConversionRunner? = nil) {
        self.defaults = defaults
        self.runner = runner ?? ConversionRunner()
        self.permissions = ConversionPermissions(defaults: defaults)
        restore()
    }
    var effectiveChunks: Bool { settings.chunks && settings.format != "html" }
    func authorizeWorkingFolders() {
        guard !isRunning else { return }
        defer { permissions.release() }
        do {
            let folders = try permissions.authorizeFolders()
            status = "Remembered access to \(folders.count) working folder(s) for GUI and CLI runs. Your output destination is unchanged."
        } catch {
            if (error as NSError).code == NSUserCancelledError { return }
            let alert = NSAlert()
            alert.icon = NSApp.applicationIconImage
            alert.messageText = "Could not remember folder access"
            alert.informativeText = error.localizedDescription
            alert.runModal()
        }
    }

    var hasAccessFailure: Bool {
        ConversionPermissions.isAccessFailure((errorMessage ?? "") + "\n" + failureDetails)
    }

    func openFileAccessSettings() {
        status = ConversionPermissions.privacyAdvice
        // Use the public application-opening API, not an undocumented pane URL.
        if let settings = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.apple.systempreferences") {
            NSWorkspace.shared.open(settings)
        }
    }
    var cancelButtonTitle: String {
        if isCancelling { return "Cancelling…" }
        if isRunning { return "Cancel" }
        return batchFinished || files.isEmpty ? "Quit" : "Cancel"
    }

    func restore() {
        if let data = defaults.data(forKey: "export-settings-v1"), let saved = try? JSONDecoder().decode(ExportSettings.self, from: data) { settings = saved }
        closeOnSuccess = defaults.bool(forKey: "close-on-success")
        adjustTimeZone = defaults.bool(forKey: "adjust-time-zone")
        timeZoneIdentifier = defaults.string(forKey: "display-time-zone") ?? TimeZone.current.identifier
        turnIndex = defaults.bool(forKey: "turn-index")
        let savedToolJSON = defaults.string(forKey: "tool-json") ?? "readable"
        toolJSON = ["readable", "pretty", "raw"].contains(savedToolJSON) ? savedToolJSON : "readable"
        destination = restoreBookmark("destination-bookmark")
        destinationNeedsSelection = defaults.data(forKey: "destination-bookmark") != nil && destination == nil
        css = restoreBookmark("css-bookmark")
    }

    private func restoreBookmark(_ key: String) -> URL? {
        guard let data = defaults.data(forKey: key) else { return nil }
        var stale = false
        do {
            let url = try URL(resolvingBookmarkData: data, options: [.withSecurityScope, .withoutUI], relativeTo: nil, bookmarkDataIsStale: &stale)
            if stale { status = "A saved permission expired. Please choose the folder or CSS file again."; return nil }
            return url
        } catch { status = "A saved location is unavailable. Please choose it again."; return nil }
    }

    private func persist() throws {
        let data = try JSONEncoder().encode(settings)
        for (key, url) in [("destination-bookmark", destination), ("css-bookmark", css)] {
            if let url { defaults.set(try url.bookmarkData(options: [.withSecurityScope], includingResourceValuesForKeys: nil, relativeTo: nil), forKey: key) }
            else { defaults.removeObject(forKey: key) }
        }
        defaults.set(data, forKey: "export-settings-v1")
        defaults.set(closeOnSuccess, forKey: "close-on-success")
        defaults.set(adjustTimeZone, forKey: "adjust-time-zone")
        defaults.set(timeZoneIdentifier, forKey: "display-time-zone")
        defaults.set(turnIndex, forKey: "turn-index")
        defaults.set(toolJSON, forKey: "tool-json")
    }

    func chooseFiles() {
        guard !isRunning else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.json, .zip, UTType("ai.unixwzrd.loggpt.archive") ?? UTType(importedAs: "ai.unixwzrd.loggpt.archive", conformingTo: .zip)]
        panel.allowsMultipleSelection = true
        panel.message = "Choose conversation JSON or LogGPT archives (.lgpt or .zip)."
        if panel.runModal() == .OK { addFiles(panel.urls) }
    }

    func addFiles(_ urls: [URL]) {
        guard !isRunning else { return }
        for url in urls {
            guard ["json", "lgpt", "zip"].contains(url.pathExtension.lowercased()) else { status = "Unsupported input: \(url.lastPathComponent). Choose JSON, LGPT or ZIP files."; continue }
            if !files.contains(where: { $0.url.resolvingSymlinksInPath() == url.resolvingSymlinksInPath() }) { files.append(InputRow(url: url)) }
        }
        showConfiguration?()
    }

    func chooseDestination() {
        guard !isRunning else { return }
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.directoryURL = destination
        if panel.runModal() == .OK { destination = panel.url; destinationNeedsSelection = false }
    }

    func clearDestination() {
        guard !isRunning else { return }
        destination = nil
        destinationNeedsSelection = false
    }

    func chooseCSS() {
        guard !isRunning else { return }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "css") ?? .text]
        if panel.runModal() == .OK { css = panel.url; settings.useCSS = true }
    }

    func viewCSS() {
        do {
            if settings.useCSS && css == nil {
                throw NSError(domain: "ExtractChat", code: 2, userInfo: [NSLocalizedDescriptionKey: "Choose a CSS file or disable custom styling to view the default stylesheet."])
            }
            let bundled = Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/ExtractChatEngine.app/Contents/Resources/default.css")
            stylesheetPreview = try StylesheetPreview.load(custom: settings.useCSS ? css : nil, bundled: bundled)
        } catch {
            let alert = NSAlert()
            alert.icon = NSApp.applicationIconImage
            alert.messageText = "Could not open the stylesheet"
            alert.informativeText = error.localizedDescription
            alert.runModal()
        }
    }

    func installCLI() {
        guard !isRunning else { return }
        guard let executable = Bundle.main.executableURL else { return }
        do {
            let destination = NSSavePanel()
            destination.title = "Install extract-chat Command"
            destination.message = "Save the launcher in a directory on your PATH. It uses this app and updates with it; keep the app at its current location. Existing commands and shell profiles will not be changed."
            destination.nameFieldStringValue = "extract-chat"
            destination.canCreateDirectories = true
            destination.directoryURL = URL(fileURLWithPath: "/usr/local/bin", isDirectory: true)
            guard destination.runModal() == .OK, let target = destination.url else { return }
            let targetScoped = target.startAccessingSecurityScopedResource()
            defer { if targetScoped { target.stopAccessingSecurityScopedResource() } }
            try CLIInstaller.install(executable: executable, to: target)
            cliInstallationMessage = "Installed \(target.path). Keep this app at its current location. Downloads/Documents use macOS file privacy permissions; --grant-access is a fallback for other folders. CLI destinations and options do not use GUI settings."
        } catch {
            cliInstallationMessage = "CLI installation failed: \(error.localizedDescription)"
            let alert = NSAlert()
            alert.icon = NSApp.applicationIconImage
            alert.messageText = "Could not install the CLI launcher"
            alert.informativeText = error.localizedDescription
            alert.runModal()
            return
        }
    }

    var validation: String? {
        if files.isEmpty { return "Choose at least one conversation file." }
        if !["readable", "pretty", "raw"].contains(toolJSON) { return "Choose a valid Tool JSON display mode." }
        if adjustTimeZone && !Self.validTimeZone(timeZoneIdentifier) { return "Choose an IANA time zone such as America/Chicago, UTC, or an offset such as UTC+05:30." }
        if destinationNeedsSelection { return "The saved destination is unavailable. Use Choose Folder to select it again, or Clear to explicitly save beside each input." }
        if settings.useCSS && settings.format != "markdown" && css == nil { return "Choose a CSS file or disable custom styling." }
        if effectiveChunks {
            guard let bytes = Int(settings.maxBytes), (1...524288).contains(bytes) else { return "Maximum chunk bytes must be between 1 and 524288." }
            for (label, value) in [("Line limit", settings.maxLines), ("Token limit", settings.maxTokens)] {
                if !value.isEmpty && (Int(value) ?? 0) <= 0 { return "\(label) must be a positive integer or blank." }
            }
            if settings.overlap != "none" && (Int(settings.overlapValue) ?? -1) < 0 { return "Overlap must be a nonnegative integer." }
            if (Int(settings.uploadBatch) ?? 0) < 1 { return "Upload batch size must be positive." }
        }
        return nil
    }

    func plannedDestinations() -> [URL] {
        var reserved: Set<String> = []
        return files.map { row in
            let source = row.url.resolvingSymlinksInPath()
            let root = destination ?? source.deletingLastPathComponent()
            let name = source.deletingPathExtension().lastPathComponent
            var result = root.appendingPathComponent(name)
            var ordinal = 2
            while reserved.contains(result.path.lowercased()) || (!settings.overwrite && FileManager.default.fileExists(atPath: result.path)) {
                result = root.appendingPathComponent("\(name)-\(ordinal)"); ordinal += 1
            }
            reserved.insert(result.path.lowercased())
            return result
        }
    }

    func arguments(source: URL, output: URL) -> [String] {
        var args = ["--format", settings.format, "--output-dir", output.path]
        if adjustTimeZone { args += ["--timezone", timeZoneIdentifier] }
        if turnIndex { args.append("--turn-index") }
        args += ["--tool-json", toolJSON]
        if settings.emitTSV { args.append("--emit-tsv") }
        if settings.mediaIndex { args.append("--media-index") }
        if settings.overwrite { args.append("--force") }
        if settings.verbose { args.append("--verbose") }
        args += ["--schema-warning-detail", settings.schemaDetail]
        if settings.useCSS && settings.format != "markdown", let css { args += ["--css-file", css.path] }
        if effectiveChunks {
            args += ["--chunk", "--chunk-strategy", settings.strategy, "--chunk-max-bytes", settings.maxBytes, "--chunk-upload-batch-size", settings.uploadBatch]
            if !settings.maxLines.isEmpty { args += ["--chunk-max-lines", settings.maxLines] }
            if !settings.maxTokens.isEmpty { args += ["--chunk-max-tokens", settings.maxTokens, "--chunk-token-encoding", settings.encoding] }
            args += ["--chunk-overlap-\(settings.overlap == "none" ? "turns" : settings.overlap)", settings.overlap == "none" ? "0" : settings.overlapValue]
        }
        return args + ["--", source.path]
    }

    static func quote(_ value: String) -> String {
        let safe = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./:-")
        if !value.isEmpty && value.unicodeScalars.allSatisfy({ safe.contains($0) }) { return value }
        return "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
    var commands: String {
        guard validation == nil else { return "Select files and valid options to preview the equivalent commands." }
        let first = files[0].url
        var args = arguments(source: first, output: destination ?? first.deletingLastPathComponent())
        args.removeLast(2) // Replace the single-file operand with the complete queue.
        if destination == nil, let index = args.firstIndex(of: "--output-dir") { args.removeSubrange(index...index + 1) }
        args += ["--managed-output", "--"] + files.map { $0.url.path }
        return "extract-chat " + args.map(Self.quote).joined(separator: " ")
    }
    func copyCommands() { NSPasteboard.general.clearContents(); NSPasteboard.general.setString(commands, forType: .string) }
    func resetToDefaults() {
        guard !isRunning else { return }
        settings = ExportSettings()
        closeOnSuccess = false
        adjustTimeZone = false
        timeZoneIdentifier = TimeZone.current.identifier
        turnIndex = false
        toolJSON = "readable"
        destination = nil
        destinationNeedsSelection = false
        css = nil
        status = "Default settings restored. Select OK to save them, or Cancel to keep your previously saved settings."
    }
    @discardableResult func saveSettings() -> Bool {
        do { try persist(); return true }
        catch { showFailure("Could not save location permissions: \(error.localizedDescription)"); return false }
    }

    static func validTimeZone(_ identifier: String) -> Bool {
        if identifier == "UTC" || identifier == "GMT" || TimeZone.knownTimeZoneIdentifiers.contains(identifier) { return true }
        guard identifier.range(of: "^(UTC|GMT)[+-][0-9]{2}:[0-9]{2}$", options: .regularExpression) != nil else { return false }
        let parts = identifier.dropFirst(4).split(separator: ":")
        return (Int(parts[0]) ?? 24) < 24 && (Int(parts[1]) ?? 60) < 60
    }

    var completedCount: Int { files.filter { $0.status == "Completed" }.count }
    var finishedCount: Int { files.filter { ["Completed", "Failed", "Cancelled"].contains($0.status) }.count }
    var resultURLs: [URL] { files.compactMap(\.output) }
    var failureDetails: String {
        var sections = files.compactMap { row in row.error.map { "\(row.url.path):\n\($0)" } }
        if !diagnostics.isEmpty { sections.append("Engine diagnostics:\n" + diagnostics) }
        return sections.joined(separator: "\n\n")
    }

    func startExport() {
        guard !isRunning else { return }
        if let validation { showFailure(validation); return }
        batchFinished = false
        isRunning = true
        isCancelling = false
        cancellationAcknowledged = false
        diagnostics = ""
        errorMessage = nil
        showDetails = false
        status = "Checking input and output access…"
        for index in files.indices {
            files[index].status = "Queued"
            files[index].progress = nil
            files[index].active = false
            files[index].output = nil
            files[index].error = nil
        }
        inputIndices = Dictionary(uniqueKeysWithValues: files.enumerated().map { ($0.element.url.resolvingSymlinksInPath().standardizedFileURL.path, $0.offset) })
        do {
            try permissions.prepare(sources: files.map(\.url), destination: destination, css: settings.useCSS && settings.format != "markdown" ? css : nil)
            guard saveSettings() else { finishSetupFailure(); return }
            let first = files[0].url
            var args = arguments(source: first, output: destination ?? first.deletingLastPathComponent())
            args.removeLast(2)
            if destination == nil, let index = args.firstIndex(of: "--output-dir") { args.removeSubrange(index...index + 1) }
            args += ["--managed-output", "--progress-json", "--"] + files.map { $0.url.path }
            status = "Starting extraction…"
            try runner.start(arguments: args, events: { [weak self] events in
                events.forEach { self?.apply($0) }
            }, completion: { [weak self] code, diagnostic in self?.finish(code: code, diagnostic: diagnostic) })
        } catch {
            if (error as NSError).domain == NSCocoaErrorDomain && (error as NSError).code == NSUserCancelledError {
                status = error.localizedDescription
            } else { showFailure(error.localizedDescription) }
            finishSetupFailure()
        }
    }

    private func finishSetupFailure() {
        permissions.release()
        isRunning = false
        for index in files.indices where files[index].status == "Queued" { files[index].status = "Ready" }
        batchFinished = true
        conversionDidFinish?()
    }

    private func apply(_ event: ConversionEvent) {
        if event.event == "summary" { event.results?.forEach { apply($0) }; return }
        guard let input = event.input else { return }
        // Python emits real paths (for example /private/var), while NSURL can
        // present their macOS aliases (/var). Normalize with the same API on
        // both sides and cache the helper spelling for later progress events.
        if inputIndices[input] == nil {
            let key = URL(fileURLWithPath: input).resolvingSymlinksInPath().standardizedFileURL.path
            inputIndices[input] = inputIndices[key]
        }
        guard let index = inputIndices[input] else { return }
        switch event.event {
        case "started":
            files[index].status = "Starting"
            files[index].active = true
        case "progress":
            let names = ["reading": "Reading", "extracting": "Extracting ZIP", "processing": "Processing messages", "rendering": "Rendering", "chunking": "Writing chunks", "copying-artifacts": "Copying artifacts", "copying-source": "Saving source JSON", "finishing": "Finishing"]
            let stage = names[event.stage ?? ""] ?? "Processing"
            files[index].status = stage
            if let done = event.completed, let total = event.total, total > 0 {
                files[index].progress = min(1, max(0, Double(done) / Double(total)))
                status = "\(files[index].url.lastPathComponent): \(stage) — \(done) of \(total)"
            } else {
                files[index].progress = nil
                status = "\(files[index].url.lastPathComponent): \(stage)…"
            }
            if isCancelling { status = "Cancelling extraction and cleaning temporary files…" }
        case "finished":
            if event.status == "cancelled" { cancellationAcknowledged = true }
            files[index].active = false
            files[index].status = event.status == "completed" ? "Completed" : event.status == "cancelled" ? "Cancelled" : "Failed"
            files[index].progress = event.status == "completed" ? 1 : nil
            files[index].error = event.error
            if event.status == "completed", let output = event.output { files[index].output = URL(fileURLWithPath: output) }
        default: break
        }
    }

    private func finish(code: Int32, diagnostic: String) {
        diagnostics = diagnostic
        permissions.release()
        let cancelled = runner.cancellationRequested || code == 130
        for index in files.indices where !["Completed", "Failed", "Cancelled"].contains(files[index].status) {
            files[index].status = cancelled ? "Cancelled" : "Failed"
            files[index].active = false
            files[index].error = cancelled ? nil : diagnostic.isEmpty ? "The engine stopped without reporting a result (exit \(code))." : String(diagnostic.suffix(3000))
        }
        isRunning = false
        isCancelling = false
        let failed = files.filter { $0.status == "Failed" }.count
        let stopped = files.filter { $0.status == "Cancelled" }.count
        status = "\(completedCount) completed, \(failed) failed, \(stopped) cancelled."
        if stopped > 0 {
            status += cancellationAcknowledged ? " Temporary files were cleaned up; earlier completed results were kept." : " Earlier completed results were kept. The engine did not confirm cleanup; see Details."
        }
        if failed > 0 {
            let firstFailure = files.first { $0.status == "Failed" }
            let detail = firstFailure?.error ?? (diagnostic.isEmpty ? "The engine exited with status \(code)." : diagnostic)
            let message = (firstFailure.map { "\($0.url.lastPathComponent): " } ?? "") + String(detail.suffix(2800))
            showFailure(status + "\n" + String(message.suffix(3000)))
        } else if code != 0 && !cancelled {
            showFailure(status + "\nThe engine exited with status \(code).\n" + String(diagnostic.suffix(3000)))
        }
        batchFinished = true
        conversionDidFinish?()
        if closeOnSuccess && code == 0 && !cancelled && errorMessage == nil && !files.isEmpty && completedCount == files.count {
            closeAfterSuccessfulExport?()
        }
    }

    private func showFailure(_ message: String) {
        var message = message
        if ConversionPermissions.isAccessFailure(message) && !message.contains(ConversionPermissions.privacyAdvice) {
            message += "\n\n" + ConversionPermissions.privacyAdvice
        }
        if message.contains("Refusing to replace") { message += "\nUncheck Overwrite to create a numbered result folder without replacing existing files." }
        errorMessage = message
        status = message
        showDetails = true
    }

    func showResults() { NSWorkspace.shared.activateFileViewerSelecting(resultURLs) }

    func cancelExport() {
        guard isRunning, !isCancelling else { return }
        isCancelling = true
        status = "Cancelling extraction and cleaning temporary files…"
        runner.cancel()
    }
    func cancel() {
        if isRunning { cancelExport(); return }
        if cancelButtonTitle == "Quit" { dismissConfiguration?(); return }
        files = []
        selection = []
        settings = ExportSettings()
        restore()
        status = "Pending extraction cancelled. Previously saved settings and completed results were kept."
    }
}
