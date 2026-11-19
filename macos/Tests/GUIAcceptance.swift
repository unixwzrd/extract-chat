// A sandboxed host for the actual product view/model/runner, with isolated
// preferences so acceptance testing never changes the user's saved options.
import AppKit
import SwiftUI

@main
@MainActor
final class GUIAcceptance: NSObject, NSApplicationDelegate {
    private let model = ExportModel()
    private var window: NSWindow!

    static func main() {
        if CommandLine.arguments.dropFirst().first == "--cli" {
            exit(CLIRunner.run(arguments: Array(CommandLine.arguments.dropFirst(2))))
        }
        let app = NSApplication.shared
        let delegate = GUIAcceptance()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        app.run()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let url = Bundle.main.url(forResource: "AppIcon", withExtension: "icns"), let icon = NSImage(contentsOf: url) { NSApp.applicationIconImage = icon }
        let applicationMenu = NSMenu()
        applicationMenu.addItem(withTitle: "Quit Acceptance Host", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let menu = NSMenu(), item = NSMenuItem()
        item.submenu = applicationMenu
        menu.addItem(item)
        NSApp.mainMenu = menu
        let fileItem = NSMenuItem(), fileMenu = NSMenu(title: "File")
        fileMenu.addItem(withTitle: "Authorize Working Folders…", action: #selector(authorizeWorkingFolders), keyEquivalent: "").target = self
        fileItem.submenu = fileMenu
        menu.addItem(fileItem)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 880, height: 900), styleMask: [.titled, .closable, .resizable], backing: .buffered, defer: false)
        window.title = "Extract Chat — Acceptance"
        window.isReleasedWhenClosed = false
        window.contentView = NSHostingView(rootView: ExportView(model: model))
        window.center()
        model.showConfiguration = { [weak self] in self?.window?.makeKeyAndOrderFront(nil) }
        model.dismissConfiguration = { NSApp.terminate(nil) }
        model.closeAfterSuccessfulExport = { NSApp.terminate(nil) }
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func authorizeWorkingFolders() { model.authorizeWorkingFolders() }

    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        model.addFiles(filenames.map { URL(fileURLWithPath: $0) })
        sender.reply(toOpenOrPrint: .success)
    }
}
