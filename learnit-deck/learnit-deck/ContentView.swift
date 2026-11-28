import SwiftUI

final class AppSettings: ObservableObject {
    @Published var projectPath = UserDefaults.standard.string(forKey: "projectPath") ?? "" {
        didSet { UserDefaults.standard.set(projectPath, forKey: "projectPath") }
    }
}

struct WelcomeView: View {
    @ObservedObject var settings: AppSettings

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Set up Learnit")
                .font(.title.bold())
            Text("Select the learnit-anki project folder containing the Python environment.")
                .foregroundStyle(.secondary)
            DirectoryPicker(path: $settings.projectPath)
        }
        .padding(32)
        .frame(width: 500, alignment: .leading)
    }
}

struct ProjectSettingsView: View {
    @EnvironmentObject private var settings: AppSettings
    @State private var testing = false
    @State private var result = ""

    var body: some View {
        Form {
            Section("Python project") {
                LabeledContent("Folder") {
                    Text(settings.projectPath.isEmpty ? "Choose a folder" : settings.projectPath)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                        .truncationMode(.middle)
                        .textSelection(.enabled)
                }
                DirectoryPicker(path: $settings.projectPath)
            }
            Section("Configuration") {
                Button(testing ? "Checking…" : "Test setup", action: testSetup)
                    .disabled(testing || settings.projectPath.isEmpty)
                if !result.isEmpty {
                    ScrollView {
                        Text(result)
                            .font(.caption.monospaced())
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 160)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 540)
    }

    private func testSetup() {
        let project = settings.projectPath
        testing = true
        result = ""
        Task {
            defer { testing = false }
            do {
                result = try await Task.detached {
                    try AppCLI.run(project, command: "test", arguments: [])
                }.value
            } catch {
                result = error.localizedDescription
            }
        }
    }
}

private struct DirectoryPicker: View {
    @Binding var path: String

    var body: some View {
        Button("Choose project folder…", action: selectDirectory)
    }

    private func selectDirectory() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        if !path.isEmpty { panel.directoryURL = URL(fileURLWithPath: path) }
        guard panel.runModal() == .OK, let url = panel.url else { return }

        let python = url.appendingPathComponent(".venv/bin/python")
        let script = url.appendingPathComponent("infrastructure/cli/main.py")
        guard FileManager.default.isExecutableFile(atPath: python.path),
              FileManager.default.fileExists(atPath: script.path) else {
            let alert = NSAlert()
            alert.messageText = "Choose the learnit-anki project folder"
            alert.informativeText = "The folder must contain .venv/bin/python and infrastructure/cli/main.py."
            alert.runModal()
            return
        }
        path = url.path
    }
}
