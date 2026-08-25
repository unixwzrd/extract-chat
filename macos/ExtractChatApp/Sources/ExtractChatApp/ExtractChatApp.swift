import SwiftUI
import UniformTypeIdentifiers

@main
struct ExtractChatApp: App {
    var body: some Scene {
        WindowGroup { ExportView() }
            .windowResizability(.contentSize)
    }
}

@MainActor
final class ExportModel: ObservableObject {
    enum OutputFormat: String, CaseIterable, Identifiable {
        case markdown, html, both
        var id: String { rawValue }
    }

    @Published var input: URL?
    @Published var destination: URL?
    @Published var format: OutputFormat = .both
    @Published var createChunks = true
    @Published var emitTSV = true
    @Published var status = "Choose a LogGPT JSON or ZIP archive."
    @Published var running = false

    private func helperURL() -> URL? {
        if let bundled = Bundle.main.url(forResource: "extract-chat", withExtension: nil),
           FileManager.default.isExecutableFile(atPath: bundled.path) { return bundled }
        let candidates = ["/opt/homebrew/bin/extract-chat", "/usr/local/bin/extract-chat"]
        return candidates.map(URL.init(fileURLWithPath:)).first {
            FileManager.default.isExecutableFile(atPath: $0.path)
        }
    }

    func export() {
        guard let input, let destination else {
            status = "Choose both an input and destination."
            return
        }
        guard let helper = helperURL() else {
            status = "The extract-chat helper is not installed or bundled."
            return
        }
        running = true
        status = "Exporting…"
        let selectedFormat = format.rawValue
        let shouldCreateChunks = createChunks
        let shouldEmitTSV = emitTSV
        let inputAccess = input.startAccessingSecurityScopedResource()
        let outputAccess = destination.startAccessingSecurityScopedResource()
        Task.detached {
            defer {
                if inputAccess { input.stopAccessingSecurityScopedResource() }
                if outputAccess { destination.stopAccessingSecurityScopedResource() }
            }
            let process = Process()
            process.executableURL = helper
            var arguments = [input.path, "--output-dir", destination.path, "--format", selectedFormat]
            if shouldCreateChunks { arguments.append("--chunk") }
            if shouldEmitTSV { arguments.append("--emit-tsv") }
            process.arguments = arguments
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            do {
                try process.run()
                process.waitUntilExit()
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let log = String(decoding: data, as: UTF8.self)
                await MainActor.run {
                    self.running = false
                    self.status = process.terminationStatus == 0 ? "Export complete." : "Export failed:\n\(log)"
                }
            } catch {
                await MainActor.run {
                    self.running = false
                    self.status = "Could not run helper: \(error.localizedDescription)"
                }
            }
        }
    }
}

struct ExportView: View {
    @StateObject private var model = ExportModel()
    @State private var choosingInput = false
    @State private var choosingDestination = false

    var body: some View {
        Form {
            LabeledContent("Conversation") {
                Button(model.input?.lastPathComponent ?? "Choose JSON or ZIP…") { choosingInput = true }
            }
            LabeledContent("Destination") {
                Button(model.destination?.path(percentEncoded: false) ?? "Choose Folder…") { choosingDestination = true }
            }
            Picker("Format", selection: $model.format) {
                ForEach(ExportModel.OutputFormat.allCases) { Text($0.rawValue.capitalized).tag($0) }
            }
            Toggle("Create continuity chunks (512 KiB maximum)", isOn: $model.createChunks)
            Toggle("Convert embedded tables to TSV", isOn: $model.emitTSV)
            HStack {
                Button("Export", action: model.export).keyboardShortcut(.defaultAction).disabled(model.running)
                if model.running { ProgressView().controlSize(.small) }
            }
            Text(model.status).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
        }
        .formStyle(.grouped)
        .frame(width: 620, height: 360)
        .fileImporter(isPresented: $choosingInput, allowedContentTypes: [.json, .zip]) { result in
            if case .success(let url) = result { model.input = url }
        }
        .fileImporter(isPresented: $choosingDestination, allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result { model.destination = url }
        }
    }
}
