import AppKit

@main
struct ExecutionSmoke {
    @MainActor static func waitFor(_ condition: () -> Bool) async throws {
        let deadline = Date().addingTimeInterval(20)
        while !condition() {
            precondition(Date() < deadline, "Timed out waiting for the helper/UI state")
            try await Task.sleep(nanoseconds: 10_000_000)
        }
    }

    @MainActor static func main() async throws {
        let manager = FileManager.default
        let root = manager.temporaryDirectory.appendingPathComponent("extract-chat-execution-\(UUID().uuidString)").resolvingSymlinksInPath()
        try manager.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? manager.removeItem(at: root) }
        let helper = root.appendingPathComponent("fixture-engine")
        // Test-only subprocess fixture. Production never uses system Python.
        let code = #"""
        #!/usr/bin/python3
        import json, pathlib, sys, tempfile, time
        def emit(data, newline=True):
            data = {"protocol_version": 1, **data}
            with (pathlib.Path(__file__).parent / "events.ndjson").open("a", encoding="utf-8") as trace:
                trace.write(json.dumps(data, ensure_ascii=False) + "\n")
            encoded = json.dumps(data, ensure_ascii=False).encode() + (b"\n" if newline else b"")
            for position in range(0, len(encoded), 7):
                sys.stdout.buffer.write(encoded[position:position + 7])
                sys.stdout.buffer.flush()
        operands = sys.argv[sys.argv.index("--") + 1:]
        records = []
        for name in operands:
            source = pathlib.Path(name).resolve()
            emit({"event": "started", "input": str(source)})
            if source.name == "bad.json":
                record = {"event": "finished", "input": str(source), "status": "failed", "error": "Malformed conversation fixture"}
            elif source.name == "cancel.json":
                try:
                    with tempfile.TemporaryDirectory(prefix=".extract-chat-", dir=source.parent):
                        emit({"event": "progress", "input": str(source), "stage": "processing", "completed": 1, "total": 100})
                        time.sleep(60)
                except KeyboardInterrupt:
                    record = {"event": "finished", "input": str(source), "status": "cancelled"}
                    emit(record)
                    records.append(record)
                    for pending in operands[len(records):]:
                        records.append({"event": "finished", "input": str(pathlib.Path(pending).resolve()), "status": "cancelled"})
                    emit({"event": "summary", "results": records}, newline=False)
                    sys.exit(130)
            else:
                sys.stderr.write("diagnostic\n" * 100000)
                sys.stderr.flush()
                emit({"event": "progress", "input": str(source), "stage": "rendering"})
                if source.name == "protocol.json":
                    print("not a protocol event", flush=True)
                output = source.parent / source.stem
                output.mkdir(exist_ok=True)
                (output / "fixture.md").write_text("fixture", encoding="utf-8")
                record = {"event": "finished", "input": str(source), "status": "completed", "output": str(output)}
            records.append(record)
            emit(record)
        emit({"event": "summary", "results": records}, newline=False)
        sys.exit(1 if any(r["status"] == "failed" for r in records) else 0)
        """#
        try code.write(to: helper, atomically: true, encoding: .utf8)
        try manager.setAttributes([.posixPermissions: 0o700], ofItemAtPath: helper.path)
        var inputs: [String: URL] = [:]
        for name in ["café's chat.json", "bad.json", "cancel.json", "pending.json", "protocol.json"] {
            let url = root.appendingPathComponent(name)
            try "{}".write(to: url, atomically: true, encoding: .utf8)
            inputs[name] = url
        }
        let suite = "ai.unixwzrd.ExtractChat.ExecutionTest.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        let model = ExportModel(defaults: defaults, runner: ConversionRunner(executable: helper))
        var closeRequests = 0
        var idleQuitRequests = 0
        model.dismissConfiguration = { idleQuitRequests += 1 }
        model.closeAfterSuccessfulExport = { closeRequests += 1 }
        model.closeOnSuccess = true
        precondition(model.files.isEmpty && model.destination == nil)
        model.addFiles([inputs["bad.json"]!, inputs["café's chat.json"]!])
        model.startExport()
        model.startExport() // Duplicate OK must not start another process.
        precondition(model.cancelButtonTitle == "Cancel")
        model.addFiles([inputs["pending.json"]!])
        precondition(model.files.count == 2 && model.isRunning)
        try await waitFor { !model.isRunning }
        let eventTrace = try String(contentsOf: root.appendingPathComponent("events.ndjson"), encoding: .utf8)
        precondition(model.files.map(\.status) == ["Failed", "Completed"], "\(model.files.map(\.status))\nExpected: \(model.files.map { $0.url.resolvingSymlinksInPath().standardizedFileURL.path })\n\(eventTrace)\n\(model.status)")
        precondition(model.completedCount == 1 && model.errorMessage?.contains("Malformed") == true)
        precondition(closeRequests == 0 && model.showDetails, "Partial failure must immediately show details, never auto-close")
        precondition(model.cancelButtonTitle == "Quit", "A finished, partially failed batch can be quit")
        model.addFiles([inputs["bad.json"]!])
        precondition(model.cancelButtonTitle == "Quit", "Duplicate inputs must not prepare a new batch")
        model.selection = [model.files[0].id]
        precondition(model.cancelButtonTitle == "Quit", "Selecting a row is not a queue edit")
        model.addFiles([inputs["pending.json"]!])
        precondition(model.cancelButtonTitle == "Cancel", "Adding input after a batch resets the action")
        precondition(model.failureDetails.contains("bad.json") && model.failureDetails.contains("Malformed conversation fixture"))
        precondition(model.resultURLs.first?.deletingLastPathComponent().resolvingSymlinksInPath() == root.resolvingSymlinksInPath())
        precondition(model.diagnostics.utf8.count <= 16384)
        precondition(!model.commands.contains("--progress-json"))
        model.files = []
        model.addFiles([inputs["café's chat.json"]!, inputs["cancel.json"]!, inputs["pending.json"]!])
        model.startExport()
        try await waitFor { model.files[1].status == "Processing messages" }
        model.cancel()
        model.cancel()
        precondition(model.cancelButtonTitle == "Cancelling…")
        precondition(idleQuitRequests == 0, "Cancel while extracting must stop the batch without quitting the application")
        try await waitFor { !model.isRunning }
        precondition(model.files.map(\.status) == ["Completed", "Cancelled", "Cancelled"])
        precondition(model.errorMessage == nil && model.status.contains("cleaned up"))
        precondition(model.cancelButtonTitle == "Quit", "A cancelled batch is finished once cleanup completes")
        precondition(closeRequests == 0 && !model.showDetails, "Cancellation must keep the app open without a failure dialog")
        let remaining = try manager.contentsOfDirectory(atPath: root.path)
        precondition(remaining.allSatisfy { !$0.hasPrefix(".extract-chat-") })
        model.files = []
        model.addFiles([inputs["café's chat.json"]!])
        model.startExport()
        try await waitFor { !model.isRunning }
        precondition(model.completedCount == 1 && model.errorMessage == nil)
        precondition(closeRequests == 1 && !model.showDetails)
        precondition(model.cancelButtonTitle == "Quit")
        let completedResults = model.resultURLs
        model.cancel()
        precondition(idleQuitRequests == 1 && model.resultURLs == completedResults, "Finished Quit exits without clearing the results")
        model.selection = Set(model.files.map(\.id))
        model.addFiles([inputs["pending.json"]!])
        model.files.removeAll { model.selection.contains($0.id) }
        precondition(model.cancelButtonTitle == "Cancel", "Removing prior input leaves a new pending queue")
        model.files = []
        model.addFiles([inputs["café's chat.json"]!])
        model.closeOnSuccess = false
        model.startExport()
        try await waitFor { !model.isRunning }
        precondition(closeRequests == 1, "A successful conversion stays open when auto-close is off")
        model.closeOnSuccess = true
        model.files = []
        model.addFiles([inputs["protocol.json"]!])
        model.startExport()
        try await waitFor { !model.isRunning }
        precondition(model.errorMessage?.contains("invalid progress event") == true)
        precondition(closeRequests == 1 && model.showDetails, "Protocol failure must not auto-close even when rows reported completion")
        let missing = ExportModel(defaults: defaults, runner: ConversionRunner(executable: root.appendingPathComponent("missing")))
        missing.closeAfterSuccessfulExport = { closeRequests += 1 }
        missing.addFiles([inputs["café's chat.json"]!])
        missing.startExport()
        precondition(!missing.isRunning && missing.errorMessage?.contains("engine is missing") == true)
        precondition(missing.showDetails)
        precondition(missing.cancelButtonTitle == "Quit", "Setup errors also end the attempt")
        precondition(closeRequests == 1)
        print("Headless runner/model: UTF-8 events, pipe drains, partial failure, cancellation cleanup, reuse, protocol/missing-helper failures, automatic failure details and success-only close passed.")
    }
}
