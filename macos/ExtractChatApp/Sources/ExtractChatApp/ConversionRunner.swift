import Foundation

struct ConversionEvent: Decodable, Sendable {
    var protocol_version: Int?
    var event: String
    var input: String?
    var stage: String?
    var completed: Int?
    var total: Int?
    var output: String?
    var status: String?
    var error: String?
    var warnings: Int?
    var results: [ConversionEvent]?
}

private final class HelperOutput: @unchecked Sendable {
    private let lock = NSLock()
    private var tail = Data()
    private var invalidProtocol = false

    func diagnostic(_ data: Data) {
        lock.lock()
        defer { lock.unlock() }
        tail.append(data)
        if tail.count > 16384 { tail = Data(tail.suffix(16384)) }
    }

    func invalidEvent() {
        lock.lock()
        invalidProtocol = true
        lock.unlock()
    }

    var result: (String, Bool) {
        lock.lock()
        defer { lock.unlock() }
        return (String(decoding: tail, as: UTF8.self), invalidProtocol)
    }
}

/// Only the bundled helper is used in the app. An explicit URL is injectable
/// for focused subprocess tests; there is no environment/PATH CLI fallback.
@MainActor
final class ConversionRunner {
    private let executable: URL
    private var child: Process?
    private var session = UUID()
    private(set) var cancellationRequested = false
    var isRunning: Bool { child != nil }

    init(executable: URL? = nil) {
        self.executable = executable ?? Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/ExtractChatEngine.app/Contents/MacOS/extract-chat")
    }

    func start(arguments: [String], events: @escaping @MainActor ([ConversionEvent]) -> Void,
               completion: @escaping @MainActor (Int32, String) -> Void) throws {
        guard child == nil else { throw CocoaError(.executableLoad) }
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            throw NSError(domain: "ExtractChat", code: 1, userInfo: [NSLocalizedDescriptionKey: "The bundled conversion engine is missing. Rebuild the application in Xcode; no external Python or CLI will be used."])
        }
        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        process.environment = ["PATH": "/usr/bin:/bin", "HOME": NSHomeDirectory(), "TMPDIR": NSTemporaryDirectory(), "PYTHONUNBUFFERED": "1"]
        let stdout = Pipe(), stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr
        let output = HelperOutput()
        let drained = DispatchGroup()
        drained.enter()
        drained.enter()
        cancellationRequested = false
        let run = UUID()
        session = run
        process.terminationHandler = { [weak self] process in
            // Both streams are drained concurrently; never wait for the child
            // on the main thread or finish before the final JSON line arrives.
            drained.notify(queue: .global(qos: .userInitiated)) {
                DispatchQueue.main.async {
                    guard let self, self.session == run else { return }
                    self.child = nil
                    let (diagnostic, invalid) = output.result
                    let message = invalid ? diagnostic + "\nThe engine returned an invalid progress event." : diagnostic
                    completion(invalid && process.terminationStatus == 0 ? 1 : process.terminationStatus, message)
                }
            }
        }
        child = process
        do { try process.run() }
        catch {
            child = nil
            process.terminationHandler = nil
            throw error
        }
        try? stdout.fileHandleForWriting.close()
        try? stderr.fileHandleForWriting.close()
        DispatchQueue.global(qos: .userInitiated).async {
            defer { try? stderr.fileHandleForReading.close(); drained.leave() }
            while true {
                let data = stderr.fileHandleForReading.availableData
                if data.isEmpty { break }
                output.diagnostic(data)
            }
        }
        DispatchQueue.global(qos: .userInitiated).async {
            defer { try? stdout.fileHandleForReading.close(); drained.leave() }
            var buffer = Data()
            func decode(_ line: Data) -> ConversionEvent? {
                guard !line.isEmpty else { return nil }
                guard let event = try? JSONDecoder().decode(ConversionEvent.self, from: line), event.protocol_version == 1 else {
                    output.invalidEvent()
                    return nil
                }
                return event
            }
            while true {
                let data = stdout.fileHandleForReading.availableData
                if data.isEmpty { break }
                buffer.append(data)
                var batch: [ConversionEvent] = []
                while let end = buffer.firstIndex(of: 10) {
                    if let event = decode(Data(buffer[..<end])) {
                        if event.event == "progress", batch.last?.event == "progress", batch.last?.input == event.input {
                            batch[batch.count - 1] = event
                        } else { batch.append(event) }
                    }
                    buffer.removeSubrange(...end)
                }
                if buffer.count > 8 * 1024 * 1024 { output.invalidEvent(); buffer.removeAll() }
                if !batch.isEmpty {
                    let delivered = batch
                    DispatchQueue.main.async { events(delivered) }
                }
            }
            if let event = decode(buffer) { DispatchQueue.main.async { events([event]) } }
        }
    }

    func cancel() {
        guard let child, child.isRunning, !cancellationRequested else { return }
        cancellationRequested = true
        // The Python job catches KeyboardInterrupt and unwinds its staging
        // directory before reporting cancellation. Do not kill it mid-cleanup.
        child.interrupt()
    }
}
