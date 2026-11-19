import AppKit
import Darwin

// Forward signals even when only the parent PID, not the process group, is sent
// a signal. Caught dispositions reset to defaults when the child execs.
private var cliChildPID: pid_t = 0
private func forwardCLISignal(_ number: Int32) {
    if cliChildPID > 0 { _ = kill(cliChildPID, number) }
}

@MainActor
enum CLIRunner {
    static let help = """

    macOS folder access (app-installed CLI only):
      --grant-access [FOLDER]  Choose and remember working folders using macOS.
                               Run separately from conversion options.
      --list-access            List remembered folder locations (not an access test).
      --forget-access FOLDER   Forget a saved folder grant; does not delete files.

    Downloads and Documents use macOS Files & Folders privacy approval.
    Documents access is a sandbox-exception candidate pending App Review.
    Enable denied access in System Settings > Privacy & Security > Files & Folders.
    Authorize other locations explicitly; normal runs never open our folder picker.
    macOS itself may ask on first access. Set up access before unattended jobs.
    --output/--output-dir control destinations, independently of GUI preferences.

    """

    static func run(arguments: [String]) -> Int32 {
        let permissions = ConversionPermissions()
        defer { permissions.release() }
        if arguments.first == "--grant-access" {
            guard arguments.count <= 2 else {
                diagnostic("Use: extract-chat --grant-access [FOLDER] (separate from conversion options).")
                return 2
            }
            let suggested = arguments.count == 2 ? folderURL(arguments[1]) : nil
            let app = NSApplication.shared
            app.setActivationPolicy(.accessory)
            app.finishLaunching()
            app.activate(ignoringOtherApps: true)
            do {
                let folders = try permissions.authorizeFolders(suggested: suggested, title: "Authorize CLI Working Folders")
                for folder in folders { diagnostic("Remembered access: \(folder.path)") }
                return 0
            } catch {
                diagnostic(error.localizedDescription)
                return (error as NSError).code == NSUserCancelledError ? 130 : 1
            }
        }
        if arguments.first == "--list-access" {
            guard arguments.count == 1 else { diagnostic("Use: extract-chat --list-access"); return 2 }
            for path in permissions.rememberedFolders { output(path + "\n") }
            return 0
        }
        if arguments.first == "--forget-access" {
            guard arguments.count == 2 else { diagnostic("Use: extract-chat --forget-access FOLDER"); return 2 }
            permissions.forget(folderURL(arguments[1]))
            return 0
        }
        // Permission bookmarks are shared, not GUI conversion preferences.
        permissions.restoreRememberedAccess()
        let status = execute(arguments)
        if status == 0 && (arguments == ["--help"] || arguments == ["-h"]) { output(help) }
        return status
    }

    private static func folderURL(_ path: String) -> URL {
        URL(fileURLWithPath: path, isDirectory: true, relativeTo: callerDirectory).standardizedFileURL
    }

    private static var callerDirectory: URL {
        let environment = ProcessInfo.processInfo.environment
        let path = environment["EXTRACT_CHAT_WORKING_DIRECTORY"] ?? environment["PWD"] ?? FileManager.default.currentDirectoryPath
        return URL(fileURLWithPath: path, isDirectory: true)
    }

    private static func output(_ message: String) { FileHandle.standardOutput.write(Data(message.utf8)) }
    private static func diagnostic(_ message: String) { FileHandle.standardError.write(Data("extract-chat: \(message)\n".utf8)) }

    private static func execute(_ arguments: [String]) -> Int32 {
        let process = Process(), errors = Pipe()
        process.executableURL = Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/ExtractChatEngine.app/Contents/MacOS/extract-chat")
        process.arguments = arguments
        // Python's getcwd() can be denied even after chdir succeeds. The parser
        // resolves all file options/default outputs against the captured caller
        // path, while libraries run in a known-accessible container directory.
        process.currentDirectoryURL = URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
        var environment = ProcessInfo.processInfo.environment
        for key in environment.keys where key.hasPrefix("PYTHON") || key.hasPrefix("DYLD_") {
            environment.removeValue(forKey: key)
        }
        environment["TMPDIR"] = NSTemporaryDirectory()
        environment["EXTRACT_CHAT_CALLER_DIRECTORY"] = callerDirectory.path
        if let home = ConversionPermissions.userHome { environment["HOME"] = home.path }
        environment.removeValue(forKey: "EXTRACT_CHAT_WORKING_DIRECTORY")
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        process.standardInput = FileHandle.standardInput
        process.standardOutput = FileHandle.standardOutput
        process.standardError = errors
        do {
            try process.run()
        } catch {
            diagnostic("Could not start the bundled engine in \(callerDirectory.path): \(error.localizedDescription). Check that the app is intact and the working directory exists and permits access.")
            return 126
        }
        cliChildPID = process.processIdentifier
        let previousInterrupt = signal(SIGINT, forwardCLISignal)
        let previousTerminate = signal(SIGTERM, forwardCLISignal)
        let previousHangup = signal(SIGHUP, forwardCLISignal)
        defer {
            signal(SIGINT, previousInterrupt)
            signal(SIGTERM, previousTerminate)
            signal(SIGHUP, previousHangup)
            cliChildPID = 0
        }
        // Drain stderr while the engine runs. Forward every byte, retaining
        // only a short suffix to detect a split permission diagnostic.
        var tail = "", denied = false, unmatched = false
        while true {
            let data = errors.fileHandleForReading.availableData
            if data.isEmpty { break }
            FileHandle.standardError.write(data)
            tail += String(decoding: data, as: UTF8.self)
            denied = denied || tail.contains("Operation not permitted") || tail.contains("Permission denied")
            unmatched = unmatched || tail.contains("Input or pattern has no matches")
            tail = String(tail.suffix(256))
        }
        process.waitUntilExit()
        if process.terminationStatus != 0 && denied {
            diagnostic("For Downloads/Documents, check System Settings > Privacy & Security > Files & Folders for Extract Chat or the terminal application macOS attributes access to. Other locations may need extract-chat --grant-access '/path/to/folder'. Filesystem permissions or other macOS protections can also deny access; no destination is changed.")
        }
        if process.terminationStatus != 0 && unmatched && !denied {
            diagnostic("Check the filename or pattern. If its folder has not been authorized, run extract-chat --grant-access '/path/to/folder', then retry.")
        }
        return process.terminationReason == .uncaughtSignal ? 128 + process.terminationStatus : process.terminationStatus
    }
}
