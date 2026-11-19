import SwiftUI
import UniformTypeIdentifiers

struct ExportView: View {
    @ObservedObject var model: ExportModel
    @State private var advanced = false
    @State private var contentHeight: CGFloat = 0
    @State private var footerHeight: CGFloat = 50

    var body: some View {
        GeometryReader { viewport in
            VStack(spacing: 0) {
                ScrollView(.vertical) {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Files to convert").font(.headline)
                            Spacer()
                            Button("Add Files…", action: model.chooseFiles).disabled(model.isRunning)
                            Button("Remove") { model.files.removeAll { model.selection.contains($0.id) }; model.selection = [] }.disabled(model.selection.isEmpty || model.isRunning)
                        }
                        Table(model.files, selection: $model.selection) {
                            TableColumn("Conversation") { row in Text(row.url.lastPathComponent).help(row.url.path) }
                            TableColumn("Status") { row in Text(row.status).foregroundStyle(.secondary).lineLimit(1).help(row.error ?? row.status) }.width(125)
                            TableColumn("Progress") { row in
                                if let progress = row.progress { ProgressView(value: progress) }
                                else if row.active { ProgressView().controlSize(.small) }
                                else { Text("—").foregroundStyle(.secondary) }
                            }.width(110)
                        }
                        .frame(height: 140)
                        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                            guard !model.isRunning else { return false }
                            let group = DispatchGroup()
                            var loaded: [Int: URL] = [:]
                            for (index, provider) in providers.enumerated() {
                                group.enter()
                                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                                    DispatchQueue.main.async {
                                        if let url { loaded[index] = url }
                                        group.leave()
                                    }
                                }
                            }
                            group.notify(queue: .main) { model.addFiles(loaded.keys.sorted().compactMap { loaded[$0] }) }
                            return true
                        }
                        VStack(alignment: .leading, spacing: 16) {
                            GroupBox("Output") {
                                VStack(alignment: .leading, spacing: 10) {
                                    HStack {
                                        Text("Destination:")
                                        Text(model.destination?.path ?? (model.destinationNeedsSelection ? "Saved folder unavailable — choose again" : "Beside each input")).lineLimit(1).truncationMode(.middle).help(model.destination?.path ?? "A separate result folder beside each original archive")
                                        Spacer()
                                        Button("Choose Folder…", action: model.chooseDestination)
                                        Button("Clear", action: model.clearDestination).disabled(model.destination == nil && !model.destinationNeedsSelection)
                                    }
                                    Picker("Format", selection: $model.settings.format) { Text("Markdown").tag("markdown"); Text("HTML").tag("html"); Text("Both").tag("both") }.pickerStyle(.segmented)
                                    Toggle("Include conversation index", isOn: $model.turnIndex)
                                    HStack {
                                        Toggle("Use a specific time zone", isOn: $model.adjustTimeZone)
                                        TimeZoneField(value: $model.timeZoneIdentifier).frame(maxWidth: 320).disabled(!model.adjustTimeZone)
                                    }
                                    Text("Times default to this Mac’s local zone. Choose America/Chicago for CST/CDT, UTC, or a fixed offset such as UTC+05:30. Original timestamps and filenames are unchanged.").font(.caption).foregroundStyle(.secondary)
                                    Toggle("Overwrite previous managed results", isOn: $model.settings.overwrite)
                                    Text("Otherwise a numbered result folder is created. Original input files are never replaced.").font(.caption).foregroundStyle(.secondary)
                                    Toggle("Close on successful completion", isOn: $model.closeOnSuccess)
                                        .help("Quit Extract Chat after every file succeeds. Failures and cancellations keep the app open. Remembered when you select OK.")
                                }.padding(6)
                            }
                            GroupBox("Artifacts and continuity") {
                                VStack(alignment: .leading, spacing: 8) {
                                    Toggle("Derive TSV files from embedded tables", isOn: $model.settings.emitTSV)
                                    Toggle("Write media inventory", isOn: $model.settings.mediaIndex)
                                    Toggle("Create continuity chunks for a new conversation", isOn: $model.settings.chunks).disabled(model.settings.format == "html")
                                    if model.settings.format == "html" { Text("Chunks require Markdown or Both. Saved chunk settings are retained but inactive.").font(.caption).foregroundStyle(.secondary) }
                                }.frame(maxWidth: .infinity, alignment: .leading).padding(6)
                            }
                            GroupBox {
                              DisclosureGroup("Advanced options", isExpanded: $advanced) {
                                VStack(alignment: .leading, spacing: 12) {
                                    chunkOptions.disabled(!model.effectiveChunks)
                                    Divider()
                                    HStack {
                                        Toggle("Custom HTML styling", isOn: $model.settings.useCSS)
                                        Text(model.css?.lastPathComponent ?? "No CSS selected").foregroundStyle(.secondary)
                                        Spacer()
                                        Button("Choose CSS…", action: model.chooseCSS)
                                        Button("View CSS…", action: model.viewCSS)
                                            .help("View, copy or save the stylesheet currently selected for HTML output.")
                                    }.disabled(model.settings.format == "markdown")
                                    Picker("Tool JSON", selection: $model.toolJSON) {
                                        Text("Readable JSON + Raw JSON").tag("readable")
                                        Text("Formatted JSON (escaped)").tag("pretty")
                                        Text("Original JSON (escaped)").tag("raw")
                                    }
                                    Text("Readable JSON keeps the structure but decodes string escapes for human display. Formatted and Original JSON retain escapes. Thoughts and ordinary code are unchanged.").font(.caption).foregroundStyle(.secondary)
                                    HStack {
                                        Picker("Schema warnings", selection: $model.settings.schemaDetail) { Text("Summary").tag("summary"); Text("Full details").tag("full") }
                                        Toggle("Verbose diagnostics", isOn: $model.settings.verbose)
                                    }
                                }.padding(.top, 8).padding(.leading, 10)
                              }.padding(6)
                            }
                        }.disabled(model.isRunning)
                        GroupBox {
                            VStack(alignment: .leading, spacing: 10) {
                                HStack {
                                    Text("Equivalent command(s)").font(.headline)
                                    Spacer()
                                    Button("Install CLI…", action: model.installCLI).disabled(model.isRunning)
                                        .accessibilityLabel("Install CLI").accessibilityIdentifier("install-cli")
                        .help("Save an extract-chat launcher for this app. Downloads/Documents use macOS permissions; authorize other locations only as needed. No separate companion is needed.")
                                    Button("Copy", action: model.copyCommands).disabled(model.validation != nil)
                                }
                                Text(model.commands)
                                    .font(.system(size: 12, design: .monospaced))
                                    .textSelection(.enabled)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .frame(maxWidth: .infinity, minHeight: 40, alignment: .topLeading)
                                    .padding(8).background(Color.primary.opacity(0.04)).cornerRadius(6)
                                if let message = model.cliInstallationMessage {
                                    Text(message).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
                                }
                            }.padding(6)
                        }
                        Text(model.validation ?? model.status).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
                        if model.isRunning { ProgressView("\(model.finishedCount) of \(model.files.count) files finished", value: Double(model.finishedCount), total: Double(max(1, model.files.count))) }
                    }
                    .padding(18).frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .background(measureHeight("content"))
                }
                .scrollDisabled(contentHeight <= max(0, viewport.size.height - footerHeight) + 0.5)
                HStack {
                    Button("Reset to Defaults", action: model.resetToDefaults)
                        .disabled(model.isRunning)
                        .help("Restore first-run conversion settings, destination and CSS selection. Selected inputs are kept. Select OK to save, or Cancel to undo.")
                    Button("Show Results", action: model.showResults).disabled(model.resultURLs.isEmpty)
                    Button("Details…") { model.showDetails = true }.disabled(model.errorMessage == nil && model.failureDetails.isEmpty)
                    Spacer()
                    Button(model.cancelButtonTitle, action: model.cancel).keyboardShortcut(.cancelAction).disabled(model.isCancelling)
                        .help(model.isRunning ? "Stop the extraction and keep the app open." : model.cancelButtonTitle == "Quit" ? "Quit Extract Chat." : "Discard the pending configuration without extracting or quitting.")
                    Button("OK", action: model.startExport).keyboardShortcut(.defaultAction).disabled(model.validation != nil || model.isRunning)
                }.padding(.horizontal, 18).padding(.top, 8).padding(.bottom, 18)
                    .background(measureHeight("footer"))
            }
            .onPreferenceChange(ContentHeights.self) { heights in
                guard let content = heights["content"], let footer = heights["footer"] else { return }
                if abs(contentHeight - content) > 0.5 { contentHeight = content }
                if abs(footerHeight - footer) > 0.5 { footerHeight = footer }
                model.resizeConfiguration?(content + footer)
            }
        }.frame(minWidth: 720)
        .sheet(item: $model.stylesheetPreview) { preview in
            StylesheetPreviewView(preview: preview)
        }
        .sheet(isPresented: $model.showDetails) {
            VStack(alignment: .leading) {
                HStack(spacing: 12) {
                    Image(nsImage: NSApp.applicationIconImage).resizable().scaledToFit().frame(width: 48, height: 48).accessibilityHidden(true)
                    Text(model.errorMessage == nil ? "Extraction details" : "Extraction was not successful").font(.headline)
                }
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(model.errorMessage ?? model.status).textSelection(.enabled)
                        if !model.failureDetails.isEmpty {
                            Text(model.failureDetails)
                                .font(.system(.body, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }
                HStack {
                    if model.hasAccessFailure { Button("Open System Settings…", action: model.openFileAccessSettings) }
                    Spacer()
                    Button("Close") { model.showDetails = false }.keyboardShortcut(.cancelAction)
                }
            }.padding(20).frame(minWidth: 600, minHeight: 350)
        }
    }

    private func measureHeight(_ name: String) -> some View {
        GeometryReader { geometry in Color.clear.preference(key: ContentHeights.self, value: [name: geometry.size.height]) }
    }

    private var chunkOptions: some View {
        VStack(alignment: .leading, spacing: 10) {
            Picker("Chunk boundaries", selection: $model.settings.strategy) { Text("Hybrid").tag("hybrid"); Text("Turn").tag("turn"); Text("Heading").tag("heading"); Text("Paragraph").tag("paragraph"); Text("Fixed").tag("fixed") }
            HStack(alignment: .top, spacing: 24) {
                numeric("Maximum bytes", value: $model.settings.maxBytes)
                numeric("Line limit (optional)", value: $model.settings.maxLines, placeholder: "No limit")
                numeric("Token limit (optional)", value: $model.settings.maxTokens, placeholder: "No limit")
            }
            HStack(alignment: .top, spacing: 24) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Overlap").font(.body)
                    HStack(spacing: 8) {
                        Picker("Overlap units", selection: $model.settings.overlap) { Text("None").tag("none"); Text("Turns").tag("turns"); Text("Lines").tag("lines"); Text("Bytes").tag("bytes") }
                            .labelsHidden().frame(width: 100)
                        TextField("Amount", text: $model.settings.overlapValue)
                            .textFieldStyle(.roundedBorder).font(.system(.body, design: .monospaced))
                            .frame(width: 80).accessibilityLabel("Overlap amount").disabled(model.settings.overlap == "none")
                    }
                }
                numeric("Files per upload batch", value: $model.settings.uploadBatch)
            }
            Picker("Token encoding (bundled offline)", selection: $model.settings.encoding) { Text("o200k_base").tag("o200k_base"); Text("cl100k_base").tag("cl100k_base") }.disabled(model.settings.maxTokens.isEmpty)
        }
    }

    private func numeric(_ title: String, value: Binding<String>, placeholder: String = "") -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.body).fixedSize(horizontal: true, vertical: false)
            TextField(placeholder, text: value).textFieldStyle(.roundedBorder)
                .font(.system(.body, design: .monospaced)).frame(width: 112)
                .accessibilityLabel(title)
        }
    }
}

private struct StylesheetPreviewView: View {
    let preview: StylesheetPreview
    @Environment(\.dismiss) private var dismiss
    @State private var saveError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(preview.title).font(.headline)
            Text(preview.source.path).font(.caption).foregroundStyle(.secondary).lineLimit(2).textSelection(.enabled)
            ScrollView([.horizontal, .vertical]) {
                Text(preview.content)
                    .font(.system(size: 12, design: .monospaced))
                    .textSelection(.enabled)
                    .fixedSize(horizontal: true, vertical: true)
                    .padding(10)
            }.frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .background(Color.primary.opacity(0.04)).cornerRadius(6)
            Text("Read-only. Save a copy, edit it in your preferred editor, then use Choose CSS to select it.")
                .font(.caption).foregroundStyle(.secondary)
            if let saveError { Text(saveError).foregroundStyle(.red).textSelection(.enabled) }
            HStack {
                Button("Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(preview.content, forType: .string)
                }
                Button("Save As…", action: save)
                Spacer()
                Button("Close") { dismiss() }.keyboardShortcut(.cancelAction)
            }
        }.padding(20).frame(width: 720, height: 500)
    }

    private func save() {
        let panel = NSSavePanel()
        panel.title = "Save Stylesheet"
        panel.nameFieldStringValue = preview.suggestedFilename
        panel.allowedContentTypes = [UTType(filenameExtension: "css") ?? .plainText]
        panel.canCreateDirectories = true
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            try preview.save(to: url)
            saveError = nil
        } catch { saveError = "Could not save the stylesheet: \(error.localizedDescription)" }
    }
}

private struct TimeZoneField: NSViewRepresentable {
    @Binding var value: String
    @Environment(\.isEnabled) private var isEnabled
    func makeCoordinator() -> Coordinator { Coordinator(value: $value) }
    func makeNSView(context: Context) -> NSComboBox {
        let field = NSComboBox()
        field.addItems(withObjectValues: ["UTC"] + TimeZone.knownTimeZoneIdentifiers.sorted())
        field.numberOfVisibleItems = 12
        field.completes = true
        field.isEditable = true
        field.delegate = context.coordinator
        field.setAccessibilityLabel("Display time zone")
        return field
    }
    func updateNSView(_ field: NSComboBox, context: Context) {
        context.coordinator.value = $value
        if field.stringValue != value { field.stringValue = value }
        field.isEnabled = isEnabled
    }
    final class Coordinator: NSObject, NSComboBoxDelegate {
        var value: Binding<String>
        init(value: Binding<String>) { self.value = value }
        func controlTextDidChange(_ notification: Notification) {
            if let field = notification.object as? NSComboBox { value.wrappedValue = field.stringValue }
        }
        func comboBoxSelectionDidChange(_ notification: Notification) {
            if let field = notification.object as? NSComboBox, let selected = field.objectValueOfSelectedItem as? String { value.wrappedValue = selected }
        }
    }
}

private struct ContentHeights: PreferenceKey {
    static var defaultValue: [String: CGFloat] = [:]
    static func reduce(value: inout [String: CGFloat], nextValue: () -> [String: CGFloat]) {
        value.merge(nextValue(), uniquingKeysWith: { _, latest in latest })
    }
}
