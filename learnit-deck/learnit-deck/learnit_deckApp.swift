import SwiftUI

@main
struct AnkiGeneratorApp: App {
    @StateObject private var settings = AppSettings()
    @Environment(\.openWindow) private var openWindow

    var body: some Scene {
        Window("Learnit", id: "card") {
            if settings.projectPath.isEmpty {
                WelcomeView(settings: settings)
            } else {
                StudyWorkspace(project: settings.projectPath, database: testDatabase)
                    .id(settings.projectPath)
                    .environmentObject(settings)
            }
        }
        .defaultSize(width: 1130, height: 730)
        .commands {
            CommandGroup(after: .newItem) {
                Button("Anki Export Window") { openWindow(id: "anki-export") }
                    .disabled(settings.projectPath.isEmpty)
            }
        }

        Window("Anki Export", id: "anki-export") {
            if settings.projectPath.isEmpty {
                WelcomeView(settings: settings)
            } else {
                MediaCardView().environmentObject(settings)
            }
        }
        .defaultSize(width: 960, height: 660)

        Settings {
            ProjectSettingsView()
                .environmentObject(settings)
        }
    }

    private var testDatabase: URL? {
        #if DEBUG
        if let path = UserDefaults.standard.string(forKey: "studyTestDatabase") {
            return URL(fileURLWithPath: path)
        }
        #endif
        return nil
    }
}
