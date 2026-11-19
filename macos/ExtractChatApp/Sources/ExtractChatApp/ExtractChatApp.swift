import AppKit
import SwiftUI

@main
@MainActor
struct ExtractChatApp {
    static func main() {
        if CommandLine.arguments.dropFirst().first == "--cli" {
            exit(CLIRunner.run(arguments: Array(CommandLine.arguments.dropFirst(2))))
        }
        let app = NSApplication.shared
        let delegate = ApplicationDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }
}

@MainActor
final class ApplicationDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    private let model = ExportModel()
    private var window: NSWindow?
    private var quitAfterExtraction = false
    private var desiredContentHeight: CGFloat?
    private var resizeScheduled = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let icon = bundledAppIcon() { NSApp.applicationIconImage = icon }
        let menu = NSMenu()
        let applicationItem = NSMenuItem()
        let applicationMenu = NSMenu()
        applicationMenu.addItem(withTitle: "About Extract Chat…", action: #selector(showAbout), keyEquivalent: "").target = self
        applicationMenu.addItem(.separator())
        applicationMenu.addItem(withTitle: "Quit Extract Chat", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        applicationItem.submenu = applicationMenu
        menu.addItem(applicationItem)
        let fileItem = NSMenuItem()
        let fileMenu = NSMenu(title: "File")
        let open = fileMenu.addItem(withTitle: "Open…", action: #selector(openFiles), keyEquivalent: "o")
        open.target = self
        fileMenu.addItem(withTitle: "Authorize Working Folders…", action: #selector(authorizeWorkingFolders), keyEquivalent: "").target = self
        fileItem.submenu = fileMenu
        menu.addItem(fileItem)
        let helpItem = NSMenuItem()
        let helpMenu = NSMenu(title: "Help")
        helpMenu.addItem(withTitle: "Extract Chat Support…", action: #selector(openSupport), keyEquivalent: "").target = self
        helpMenu.addItem(withTitle: "File Access Settings…", action: #selector(openFileAccessSettings), keyEquivalent: "").target = self
        helpMenu.addItem(withTitle: "Privacy Policy…", action: #selector(showPrivacy), keyEquivalent: "").target = self
        helpMenu.addItem(withTitle: "Terms of Use…", action: #selector(showTerms), keyEquivalent: "").target = self
        helpItem.submenu = helpMenu
        menu.addItem(helpItem)
        NSApp.mainMenu = menu
        NSApp.helpMenu = helpMenu
        model.showConfiguration = { [weak self] in self?.showWindow() }
        model.dismissConfiguration = { NSApp.terminate(nil) }
        model.resizeConfiguration = { [weak self] height in self?.requestHeight(height) }
        model.conversionDidFinish = { [weak self] in
            if self?.quitAfterExtraction == true { NSApp.reply(toApplicationShouldTerminate: true) }
        }
        model.closeAfterSuccessfulExport = { NSApp.terminate(nil) }
        NotificationCenter.default.addObserver(self, selector: #selector(screenParametersChanged), name: NSApplication.didChangeScreenParametersNotification, object: nil)
        showWindow()
    }

    private func showWindow() {
        if window == nil {
            let created = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 880, height: 760), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
            created.title = "Extract Chat"
            created.isReleasedWhenClosed = false
            created.delegate = self
            created.minSize = NSSize(width: 760, height: 650)
            created.contentView = NSHostingView(rootView: ExportView(model: model))
            created.center()
            window = created
        }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func requestHeight(_ height: CGFloat) {
        guard height.isFinite, height > 0 else { return }
        desiredContentHeight = height
        guard !resizeScheduled else { return }
        resizeScheduled = true
        // Coalesce geometry updates; measuring natural content must not cause
        // a recursive window-layout/resize loop.
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.resizeScheduled = false
            guard let window = self.window, let height = self.desiredContentHeight,
                  let screen = window.screen ?? NSScreen.main else { return }
            let chrome = window.frame.height - window.contentRect(forFrameRect: window.frame).height
            let target = WindowSizing.frame(current: window.frame, contentHeight: height, chromeHeight: chrome, visible: screen.visibleFrame)
            window.minSize.height = min(650, screen.visibleFrame.height)
            if abs(target.height - window.frame.height) > 0.5 || abs(target.minY - window.frame.minY) > 0.5 {
                window.setFrame(target, display: true, animate: false)
            }
        }
    }

    func windowDidChangeScreen(_ notification: Notification) { screenParametersChanged() }

    @objc private func screenParametersChanged() {
        if let height = desiredContentHeight { requestHeight(height) }
    }

    @objc private func openFiles() { model.chooseFiles() }

    @objc private func authorizeWorkingFolders() { model.authorizeWorkingFolders() }

    @objc private func openFileAccessSettings() { model.openFileAccessSettings() }

    @objc private func openSupport() {
        NSWorkspace.shared.open(URL(string: "https://unixwzrd.ai/projects/extract-chat/")!)
    }

    @objc private func showAbout() {
        let text = "MIT License\n\nWebsite · Privacy Policy · Terms of Use"
        let style = NSMutableParagraphStyle()
        style.alignment = .center
        let credits = NSMutableAttributedString(string: text, attributes: [
            .font: NSFont.systemFont(ofSize: 12), .paragraphStyle: style,
        ])
        for (label, address) in [
            ("MIT License", "https://github.com/unixwzrd/extract-chat/blob/main/LICENSE"),
            ("Website", "https://unixwzrd.ai/projects/extract-chat/"),
            ("Privacy Policy", "https://unixwzrd.ai/Policies/Privacy_Extract_Chat/"),
            ("Terms of Use", "https://unixwzrd.ai/Policies/Terms_Extract_Chat/"),
        ] {
            credits.addAttribute(.link, value: URL(string: address)!, range: (text as NSString).range(of: label))
        }
        var options: [NSApplication.AboutPanelOptionKey: Any] = [.applicationName: "Extract Chat", .credits: credits]
        if let icon = bundledAppIcon() { options[.applicationIcon] = icon }
        NSApp.orderFrontStandardAboutPanel(options: options)
    }

    private func bundledAppIcon() -> NSImage? {
        // Read our signed resource directly rather than relying on an implicit
        // application-icon lookup, which can still yield the placeholder.
        guard let url = Bundle.main.url(forResource: "AppIcon", withExtension: "icns") else { return nil }
        return NSImage(contentsOf: url)
    }

    @objc private func showPrivacy() {
        NSWorkspace.shared.open(URL(string: "https://unixwzrd.ai/Policies/Privacy_Extract_Chat/")!)
    }

    @objc private func showTerms() {
        NSWorkspace.shared.open(URL(string: "https://unixwzrd.ai/Policies/Terms_Extract_Chat/")!)
    }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        guard !model.isRunning else { sender.reply(toOpenOrPrint: .failure); return }
        model.addFiles(filenames.map { URL(fileURLWithPath: $0) })
        DispatchQueue.main.async { self.showWindow() }
        sender.reply(toOpenOrPrint: .success)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { showWindow() }
        return true
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        guard model.isRunning else { return true }
        model.cancelExport()
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard model.isRunning else { return .terminateNow }
        let alert = NSAlert()
        alert.icon = NSApp.applicationIconImage
        alert.messageText = "Cancel extraction and quit?"
        alert.informativeText = "Completed results will be kept. The current extraction will stop and clean up its temporary files before the app quits."
        alert.addButton(withTitle: "Keep Extracting")
        alert.addButton(withTitle: "Cancel and Quit")
        guard alert.runModal() == .alertSecondButtonReturn else { return .terminateCancel }
        quitAfterExtraction = true
        model.cancelExport()
        return .terminateLater
    }
}
