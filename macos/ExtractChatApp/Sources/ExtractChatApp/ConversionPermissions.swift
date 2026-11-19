import AppKit
import Darwin

@MainActor
final class ConversionPermissions {
    private var accessing: [URL] = []
    private let defaults: UserDefaults
    private let bookmarkKey = "output-folder-access-v1"

    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    static var userHome: URL? {
        guard let entry = getpwuid(getuid()), let path = entry.pointee.pw_dir else { return nil }
        return URL(fileURLWithPath: String(cString: path), isDirectory: true)
    }

    func usesSystemFolderAccess(_ url: URL) -> Bool {
        guard let home = Self.userHome else { return false }
        return ["Downloads", "Documents"].contains { contains(home.appendingPathComponent($0, isDirectory: true), url) }
    }

    static let privacyAdvice = "For Downloads or Documents, enable access in System Settings > Privacy & Security > Files & Folders. macOS may attribute CLI access to your terminal application. Other locations can be authorized with File > Authorize Working Folders… or extract-chat --grant-access. Filesystem permissions and other macOS protections still apply."

    static func isAccessFailure(_ text: String) -> Bool {
        let text = text.lowercased()
        return ["operation not permitted", "permission denied", "cannot read", "not writable", "don’t have permission", "don't have permission", "macos denied"].contains { text.contains($0) }
    }

    private func checkInput(_ url: URL) throws {
        if usesSystemFolderAccess(url) {
            // An actual open of the requested input lets macOS handle TCC.
            // access()/isReadableFile alone can fail without showing consent.
            do {
                let file = try FileHandle(forReadingFrom: url)
                try file.close()
            } catch {
                throw failure("Cannot read \(url.path): \(error.localizedDescription)\n\(Self.privacyAdvice)")
            }
        } else if !FileManager.default.isReadableFile(atPath: url.path) {
            throw failure("Cannot read \(url.path). Download cloud files in Finder if needed, or authorize their location with File > Authorize Working Folders….")
        }
    }

    var rememberedFolders: [String] { (defaults.dictionary(forKey: bookmarkKey) ?? [:]).keys.sorted() }

    func forget(_ folder: URL) {
        var saved = defaults.dictionary(forKey: bookmarkKey) ?? [:]
        saved.removeValue(forKey: folder.resolvingSymlinksInPath().standardizedFileURL.path)
        defaults.set(saved, forKey: bookmarkKey)
    }

    func restoreRememberedAccess() {
        let saved = defaults.dictionary(forKey: bookmarkKey) ?? [:]
        for key in saved.keys.sorted() {
            guard let data = saved[key] as? Data else { continue }
            do {
                var stale = false
                let folder = try URL(resolvingBookmarkData: data, options: [.withSecurityScope, .withoutUI], relativeTo: nil, bookmarkDataIsStale: &stale)
                acquire(folder)
                if stale { try remember(folder, replacing: key) }
            } catch {
                // Revoked/unavailable bookmarks never authorize another path.
                continue
            }
        }
    }

    func authorizeFolders(suggested: URL? = nil, title: String = "Authorize Working Folders") throws -> [URL] {
        let panel = NSOpenPanel()
        panel.title = title
        panel.message = "Select folders containing your conversations, artifacts, and extraction destinations. Access includes subfolders and is remembered for GUI and CLI runs. This does not choose an output destination."
        panel.prompt = "Allow Access"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = suggested == nil
        panel.directoryURL = suggested
        guard panel.runModal() == .OK else {
            throw NSError(domain: NSCocoaErrorDomain, code: NSUserCancelledError, userInfo: [NSLocalizedDescriptionKey: "Folder authorization cancelled. No extraction was started."])
        }
        if let suggested, !panel.urls.contains(where: { contains($0, suggested) }) {
            throw failure("Select the requested folder or a parent that contains it. No permission for the requested path was remembered.")
        }
        for folder in panel.urls {
            acquire(folder)
            try remember(folder)
        }
        return panel.urls
    }

    private func contains(_ folder: URL, _ child: URL) -> Bool {
        let parent = folder.resolvingSymlinksInPath().standardizedFileURL.path
        let path = child.resolvingSymlinksInPath().standardizedFileURL.path
        return parent == path || path.hasPrefix(parent == "/" ? "/" : parent + "/")
    }

    private func remember(_ folder: URL, replacing oldKey: String? = nil) throws {
        // These are permissions, not the selected destination. Remembering a
        // source folder must never switch output away from Beside each input.
        let data = try folder.bookmarkData(options: [.withSecurityScope], includingResourceValuesForKeys: nil, relativeTo: nil)
        var saved = defaults.dictionary(forKey: bookmarkKey) ?? [:]
        if let oldKey { saved.removeValue(forKey: oldKey) }
        saved[folder.resolvingSymlinksInPath().standardizedFileURL.path] = data
        defaults.set(saved, forKey: bookmarkKey)
    }

    private func restoreAccess(to root: URL) {
        let saved = defaults.dictionary(forKey: bookmarkKey) ?? [:]
        // Activate only grants that can cover this output parent, not every
        // directory ever used by the application.
        for key in saved.keys.sorted(by: { $0.count > $1.count }) {
            guard contains(URL(fileURLWithPath: key), root), let data = saved[key] as? Data else { continue }
            do {
                var stale = false
                let folder = try URL(resolvingBookmarkData: data, options: [.withSecurityScope, .withoutUI], relativeTo: nil, bookmarkDataIsStale: &stale)
                guard contains(folder, root) else { continue }
                acquire(folder)
                guard FileManager.default.isWritableFile(atPath: root.path) else { continue }
                if stale { try remember(folder, replacing: key) }
                return
            } catch {
                // A revoked, corrupt or unavailable grant does not authorize a
                // new folder. Fall through to normal access checking/picking.
                continue
            }
        }
    }

    private func acquire(_ url: URL) {
        guard !accessing.contains(url) else { return }
        if url.startAccessingSecurityScopedResource() { accessing.append(url) }
    }

    func prepare(sources: [URL], destination: URL?, css: URL?) throws {
        restoreRememberedAccess()
        for source in sources {
            acquire(source)
            try checkInput(source)
        }
        if let css {
            acquire(css)
            try checkInput(css)
        }
        let roots = destination.map { [$0] } ?? sources.map { $0.resolvingSymlinksInPath().deletingLastPathComponent() }
        var checked: Set<String> = []
        for root in roots {
            let canonical = root.resolvingSymlinksInPath().standardizedFileURL
            guard checked.insert(canonical.path).inserted else { continue }
            acquire(root)
            // These locations are declared by the signed app. The actual
            // engine write requests system consent; do not replace a TCC denial
            // with our own folder picker or redirect the user's destination.
            if usesSystemFolderAccess(root) { continue }
            if !FileManager.default.isWritableFile(atPath: root.path) { restoreAccess(to: root) }
            if FileManager.default.isWritableFile(atPath: root.path) { continue }
            let cancelled = NSError(domain: NSCocoaErrorDomain, code: NSUserCancelledError, userInfo: [NSLocalizedDescriptionKey: "Folder access was cancelled. Nothing was extracted. Choose Folder to authorize a destination, or try OK again to save beside the input."])
            let explanation = NSAlert()
            explanation.icon = NSApp.applicationIconImage
            explanation.alertStyle = .informational
            explanation.messageText = "Select the output folder"
            let location = destination == nil ? "beside your input files" : "in your chosen destination"
            explanation.informativeText = "To save \(location), select “\(root.lastPathComponent)” in the next window. macOS needs permission to write here. Extract Chat will remember this access for next time."
            explanation.addButton(withTitle: "OK")
            explanation.addButton(withTitle: "Cancel")
            guard explanation.runModal() == .alertFirstButtonReturn else { throw cancelled }
            let panel = NSOpenPanel()
            panel.canChooseFiles = false
            panel.canChooseDirectories = true
            panel.allowsMultipleSelection = false
            panel.directoryURL = root
            panel.title = "Select Folder"
            panel.prompt = "Select Folder"
            guard panel.runModal() == .OK, let chosen = panel.url else {
                throw cancelled
            }
            guard chosen.resolvingSymlinksInPath().standardizedFileURL == canonical else {
                throw failure("That is a different folder. Use Choose Folder to change the output destination; Extract Chat will not silently redirect your results.")
            }
            acquire(chosen)
            guard FileManager.default.isWritableFile(atPath: root.path) else {
                throw failure("The folder is still not writable: \(root.path). Check its permissions or use Choose Folder.")
            }
            do { try remember(chosen) }
            catch { throw failure("Could not remember access to \(root.path): \(error.localizedDescription). No extraction was started.") }
        }
    }

    func release() {
        accessing.forEach { $0.stopAccessingSecurityScopedResource() }
        accessing.removeAll()
    }

    private func failure(_ message: String) -> NSError {
        NSError(domain: "ExtractChat.Permissions", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }
}
