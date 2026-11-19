import Foundation
import Darwin

enum CLIInstaller {
    private static func failure(_ message: String) -> NSError {
        NSError(domain: "ExtractChat.CLIInstaller", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }

    static func launcher(executable: URL) -> String {
        let quoted = "'" + executable.path.replacingOccurrences(of: "'", with: "'\\''") + "'"
        return """
        #!/bin/sh
        # Extract Chat app CLI launcher v2
        # App Sandbox changes cwd before main(); preserve the caller's directory.
        EXTRACT_CHAT_WORKING_DIRECTORY=$(pwd -P) || exit 1
        export EXTRACT_CHAT_WORKING_DIRECTORY
        tool=\(quoted)
        if [ ! -x "$tool" ]; then
            printf '%s\\n' 'Extract Chat has moved or is missing. Save a new launcher using Install CLI in the app.' >&2
            exit 127
        fi
        exec "$tool" --cli "$@"

        """
    }

    static func install(executable: URL, to destination: URL) throws {
        // Exclusive, no-follow creation preserves existing tools and dangling
        // symlinks. chmod applies to the opened descriptor, not a raced path.
        let descriptor = open(destination.path, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, mode_t(0o600))
        guard descriptor >= 0 else {
            if errno == EEXIST { throw failure("A file already exists at \(destination.path). Choose another folder; existing commands are never overwritten.") }
            throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
        }
        let file = FileHandle(fileDescriptor: descriptor, closeOnDealloc: true)
        do {
            try file.write(contentsOf: Data(launcher(executable: executable).utf8))
            guard fchmod(descriptor, mode_t(0o755)) == 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
            try file.close()
        } catch {
            try? file.close()
            try? FileManager.default.removeItem(at: destination)
            throw error
        }
    }
}
