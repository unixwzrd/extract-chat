import Foundation

@main
struct CLIInstallerSmoke {
    static func reject(_ action: () throws -> Void) {
        do { try action(); preconditionFailure("Unsafe installation was accepted") }
        catch { }
    }

    static func run(_ command: URL, _ arguments: [String], at directory: URL) throws -> (Int32, String, String) {
        let process = Process(), output = Pipe(), diagnostics = Pipe()
        process.executableURL = command
        process.arguments = arguments
        process.currentDirectoryURL = directory
        process.environment = ["PATH": "/usr/bin:/bin", "HOME": NSHomeDirectory(), "LC_ALL": "en_US.UTF-8"]
        process.standardOutput = output
        process.standardError = diagnostics
        try process.run()
        let stdout = output.fileHandleForReading.readDataToEndOfFile()
        let stderr = diagnostics.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return (process.terminationStatus, String(decoding: stdout, as: UTF8.self), String(decoding: stderr, as: UTF8.self))
    }

    static func main() throws {
        precondition(CommandLine.arguments.count == 3, "CLIInstallerSmoke APP_EXECUTABLE AUTHORIZED_TEST_FOLDER")
        let executable = URL(fileURLWithPath: CommandLine.arguments[1]).standardizedFileURL
        let parent = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
        let temporary = parent.appendingPathComponent("ExtractChat-CLI-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: temporary, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let fake = temporary.appendingPathComponent("Extract Chat's café app")
        try "#!/bin/sh\nprintf '%s\\n' \"$PWD\" \"$@\"\nexit 23\n".write(to: fake, atomically: false, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: fake.path)
        let quoting = temporary.appendingPathComponent("quoted-launcher")
        try CLIInstaller.install(executable: fake, to: quoting)
        let quoted = try run(quoting, ["--", "a'b café", "$(not-a-command); *"], at: temporary)
        precondition(quoted.0 == 23)
        precondition(quoted.1 == "\(temporary.path)\n--cli\n--\na'b café\n$(not-a-command); *\n")

        let launcher = temporary.appendingPathComponent("extract-chat")
        try CLIInstaller.install(executable: executable, to: launcher)
        let script = try Data(contentsOf: launcher)
        precondition(FileManager.default.isExecutableFile(atPath: launcher.path))
        reject { try CLIInstaller.install(executable: executable, to: launcher) }
        let unchangedScript = try Data(contentsOf: launcher)
        precondition(unchangedScript == script)
        let missing = temporary.appendingPathComponent("never-created")
        let dangling = temporary.appendingPathComponent("dangling-command")
        try FileManager.default.createSymbolicLink(at: dangling, withDestinationURL: missing)
        reject { try CLIInstaller.install(executable: executable, to: dangling) }
        precondition(!FileManager.default.fileExists(atPath: missing.path))

        let version = try run(launcher, ["--version"], at: temporary)
        precondition(version.0 == 0 && version.1.contains("extract-chat"), "Version failed: \(version)")
        let help = try run(launcher, ["--help"], at: temporary)
        precondition(help.0 == 0 && help.1.contains("--format") && help.1.contains("--grant-access"))
        let invalid = try run(launcher, ["--not-an-extract-chat-option"], at: temporary)
        precondition(invalid.0 == 2 && !invalid.2.isEmpty)
        let wrongGrant = try run(launcher, ["--grant-access", "one", "two"], at: temporary)
        precondition(wrongGrant.0 == 2 && wrongGrant.2.contains("Use:"))

        let source = temporary.appendingPathComponent("-quoted 'café' input.json")
        let raw: [String: Any] = ["title": "CLI fixture", "create_time": 100, "update_time": 101, "mapping": [
            "question": ["id": "question", "message": ["id": "question", "author": ["role": "user"], "create_time": 100, "content": ["content_type": "text", "parts": ["CLI fixture question"]]]],
            "answer": ["id": "answer", "parent": "question", "message": ["id": "answer", "author": ["role": "assistant"], "create_time": 101, "content": ["content_type": "text", "parts": ["CLI fixture **answer**.\n\n- A list item"]]]],
        ]]
        let originalData = try JSONSerialization.data(withJSONObject: raw, options: [.prettyPrinted, .sortedKeys])
        try originalData.write(to: source)
        let results = temporary.appendingPathComponent("results with spaces")
        let conversion = try run(launcher, ["--format", "both", "--managed-output", "--output-dir", results.path, "--timezone", "UTC", "--turn-index", "--chunk", "--chunk-max-tokens", "2048", "--", source.lastPathComponent], at: temporary)
        precondition(conversion.0 == 0, "Bundled CLI conversion failed: \(conversion.2)")
        let files = FileManager.default.enumerator(at: results, includingPropertiesForKeys: nil)!.allObjects.compactMap { $0 as? URL }
        precondition(files.contains { $0.pathExtension == "html" })
        precondition(files.contains { $0.lastPathComponent == "chunk-manifest.json" })
        let retained = files.first { $0.lastPathComponent == source.lastPathComponent }!
        let retainedData = try Data(contentsOf: retained)
        let unchangedInput = try Data(contentsOf: source)
        precondition(retainedData == originalData && unchangedInput == originalData)
        let bad = temporary.appendingPathComponent("bad.json")
        try Data("{bad".utf8).write(to: bad)
        let failed = try run(launcher, [bad.path], at: temporary)
        precondition(failed.0 != 0 && !failed.2.isEmpty)
        let unavailable = temporary.appendingPathComponent("missing-app-launcher")
        try CLIInstaller.install(executable: missing, to: unavailable)
        let absent = try run(unavailable, ["--version"], at: temporary)
        precondition(absent.0 == 127 && absent.2.contains("missing"))
        print("App launcher: exclusive creation, symlinks, quoting/cwd/status, clean-environment help/version/errors, authorized conversion, offline chunks and unchanged originals passed.")
    }
}
