//
//  ContentView.swift
//  learnit-deck
//
//  Created by bordumb on 20/10/2025.
//

import SwiftUI
import UniformTypeIdentifiers

// MARK: - Configuration
// An object to hold the application's settings, saved across launches.
class AppSettings: ObservableObject {
    @AppStorage("projectPath") var projectPath: String = ""
}

// MARK: - Supported Languages (For Pickers)
// Define supported languages centrally
struct Language: Identifiable, Hashable {
    let id = UUID()
    let code: String
    let name: String
}

let supportedLanguages: [Language] = [
    Language(code: "fr", name: "French"),
    Language(code: "de", name: "German"),
    Language(code: "es", name: "Spanish"),
    Language(code: "ca", name: "Catalan"),
    Language(code: "en", name: "English"),
    Language(code: "ja", name: "Japanese"),
    // Add more as needed
]

// MARK: - Welcome / Setup View
struct WelcomeView: View {
    @ObservedObject var settings: AppSettings

    var body: some View {
        VStack(spacing: 20) {
            HeaderView()
            Spacer()
            Text("Welcome to the Anki Deck Generator")
                .font(.title2)
            Text("To get started, please locate your 'learnit-anki' Python project folder.")
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            DirectoryPicker(path: $settings.projectPath)

            Text("This is a one-time setup. The app will remember this location.")
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
        }
        .frame(width: 500, height: 350)
    }
}

// MARK: - Main Content View
struct ContentView: View {
    @State private var selectedTab = 0
    @ObservedObject var settings: AppSettings

    var body: some View {
        VStack {
            HeaderView()

            TabView(selection: $selectedTab) {
                SingleSentenceView()
                    .tabItem { Label("Single Sentence", systemImage: "text.quote") }
                    .tag(0)

                TextFileView()
                    .tabItem { Label("From Text File", systemImage: "doc.text") }
                    .tag(1)

                CSVFileView()
                    .tabItem { Label("From CSV File", systemImage: "tablecells") }
                    .tag(2)

                MediaCardView()
                    .tabItem { Label("Japanese Card", systemImage: "photo.on.rectangle") }
                    .tag(4)

                SettingsView()
                    .tabItem { Label("Settings", systemImage: "gear") }
                    .tag(3)
            }
            .padding()
        }
        .frame(minWidth: 550, idealWidth: 650, maxWidth: 850, minHeight: 500, idealHeight: 600, maxHeight: 750) // Increased size slightly
        .background(Color(.windowBackgroundColor))
        .environmentObject(settings) // Pass settings to all child views
    }
}

// MARK: - Reusable UI Components
struct HeaderView: View {
    var body: some View {
        HStack {
            Image(systemName: "square.stack.3d.up.fill")
                .font(.largeTitle)
                .foregroundColor(.accentColor)
            Text("Anki Deck Generator")
                .font(.largeTitle)
                .fontWeight(.thin)
            Spacer()
        }
        .padding()
        .background(Color(.textBackgroundColor))
    }
}

// --- NEW Language Selection View ---
struct LanguageSelectionView: View {
    @Binding var sourceLang: Language
    @Binding var targetLang: Language
    let availableLangs: [Language]

    var body: some View {
        HStack {
            Picker("Source Language:", selection: $sourceLang) {
                ForEach(availableLangs) { lang in
                    Text(lang.name).tag(lang)
                }
            }
            .frame(maxWidth: .infinity)

            Image(systemName: "arrow.right")
                .foregroundColor(.secondary)

            Picker("Target Language:", selection: $targetLang) {
                ForEach(availableLangs) { lang in
                    Text(lang.name).tag(lang)
                }
            }
            .frame(maxWidth: .infinity)
        }
        .padding(.vertical, 5) // Add some vertical padding
    }
}
// --- END NEW ---


struct DeckOptionsView: View {
    @Binding var deckName: String
    @Binding var includeAudio: Bool
    @Binding var includeGrammar: Bool

    // --- NEW Language Bindings ---
    @Binding var sourceLang: Language
    @Binding var targetLang: Language
    // --- END NEW ---

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("Options") // Simplified title
                .font(.headline)
                .foregroundColor(.secondary)

            // --- NEW Language Selection ---
            LanguageSelectionView(
                sourceLang: $sourceLang,
                targetLang: $targetLang,
                availableLangs: supportedLanguages
            )
            // --- END NEW ---

            TextField("Deck Name", text: $deckName)
                .textFieldStyle(RoundedBorderTextFieldStyle())

            Toggle(isOn: $includeAudio) { Text("Include Audio (Requires Google Cloud Setup)") }
            Toggle(isOn: $includeGrammar) { Text("Include Grammar & Phrase Notes") }
        }
        .padding()
        .background(Color(.textBackgroundColor))
        .cornerRadius(10)
    }
}

struct GenerationView: View {
    let onGenerate: () -> Void
    @Binding var isGenerating: Bool
    @Binding var progressMessage: String

    var body: some View {
        VStack {
            if isGenerating {
                ProgressView(value: 0.5) // Example: Show indeterminate progress or update value later
                  .progressViewStyle(LinearProgressViewStyle())
                Text(progressMessage)
                    .foregroundColor(.secondary)
                    .font(.caption)
            } else {
                Button(action: onGenerate) {
                    Label("Generate Deck", systemImage: "play.fill")
                        .padding(.horizontal)
                }
                .keyboardShortcut(.defaultAction) // Trigger with Enter key
                .controlSize(.large) // Make button slightly larger
            }
        }
        .padding(.top) // Add padding above the button/progress bar
    }
}

// MARK: - Tab Views
struct SingleSentenceView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var sentence = ""
    @State private var deckName = "Language Practice" // More generic default
    @State private var includeAudio = false
    @State private var includeGrammar = true

    // --- NEW Language States ---
    @State private var sourceLang: Language = supportedLanguages.first { $0.code == "fr" } ?? supportedLanguages[0]
    @State private var targetLang: Language = supportedLanguages.first { $0.code == "en" } ?? supportedLanguages[1]
    // --- END NEW ---

    @State private var isGenerating = false
    @State private var progressMessage = ""

    var body: some View {
        VStack(spacing: 20) {
            TextField("Enter sentence here...", text: $sentence, axis: .vertical) // Allow multi-line
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .font(.title3)
                .lineLimit(3...) // Allow sentence field to grow
                .frame(minHeight: 60) // Give it a minimum height

            DeckOptionsView(
                deckName: $deckName,
                includeAudio: $includeAudio,
                includeGrammar: $includeGrammar,
                // --- Pass language bindings ---
                sourceLang: $sourceLang,
                targetLang: $targetLang
                // --- End pass ---
            )

            GenerationView(onGenerate: generate, isGenerating: $isGenerating, progressMessage: $progressMessage)

            Spacer() // Pushes content to the top
        }
        .padding()
    }

    func generate() {
        guard !sentence.isEmpty else {
            showAlert(title: "Input Missing", message: "Sentence cannot be empty.")
            return
        }
        guard !deckName.isEmpty else {
            showAlert(title: "Input Missing", message: "Deck Name cannot be empty.")
            return
        }
        guard sourceLang.code != targetLang.code else {
             showAlert(title: "Invalid Selection", message: "Source and Target languages cannot be the same.")
             return
         }


        let command = "add"
        // --- UPDATED arguments ---
        var args = [
            sentence,
            "--deck-name", deckName,
            "-s", sourceLang.code, // Add source language arg
            "-t", targetLang.code  // Add target language arg
        ]
        // --- END UPDATED ---
        if includeAudio { args.append("--audio") }
        if !includeGrammar { args.append("--no-grammar") }

        runGeneration(
            projectPath: settings.projectPath,
            command: command,
            args: args,
            isGenerating: $isGenerating,
            progressMessage: $progressMessage
        )
    }
}

struct TextFileView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var fileURL: URL?
    @State private var deckName = "Text File Deck"
    @State private var includeAudio = false
    @State private var includeGrammar = true

    // --- NEW Language States ---
    @State private var sourceLang: Language = supportedLanguages.first { $0.code == "fr" } ?? supportedLanguages[0]
    @State private var targetLang: Language = supportedLanguages.first { $0.code == "en" } ?? supportedLanguages[1]
    // --- END NEW ---

    @State private var isShowingFileImporter = false
    @State private var isGenerating = false
    @State private var progressMessage = ""

    var body: some View {
        VStack(spacing: 20) {
            Button(action: { isShowingFileImporter = true }) {
                HStack {
                   Image(systemName: fileURL == nil ? "doc.badge.plus" : "doc.text.fill")
                   Text(fileURL?.lastPathComponent ?? "Select a .txt file")
                }
                .padding()
                .frame(maxWidth: .infinity) // Make button wider
                .background(Color(.textBackgroundColor))
                .cornerRadius(8)
            }
            .buttonStyle(.plain) // Use plain style to allow background/cornerRadius
            .fileImporter(isPresented: $isShowingFileImporter, allowedContentTypes: [.plainText]) { result in
                if case .success(let url) = result {
                    // Ensure we have security-scoped access if needed (macOS Sandbox)
                    _ = url.startAccessingSecurityScopedResource()
                    fileURL = url
                    // Auto-fill deck name based on filename if deck name is default
                    if deckName == "Text File Deck" {
                         deckName = url.deletingPathExtension().lastPathComponent.replacingOccurrences(of: "_", with: " ").capitalized
                    }
                }
            }

            DeckOptionsView(
                deckName: $deckName,
                includeAudio: $includeAudio,
                includeGrammar: $includeGrammar,
                // --- Pass language bindings ---
                sourceLang: $sourceLang,
                targetLang: $targetLang
                // --- End pass ---
            )

            GenerationView(onGenerate: generate, isGenerating: $isGenerating, progressMessage: $progressMessage)
            Spacer()
        }
        .padding()
    }

    func generate() {
        guard let url = fileURL else {
            showAlert(title: "Input Missing", message: "Please select a text file.")
            return
        }
         guard !deckName.isEmpty else {
            showAlert(title: "Input Missing", message: "Deck Name cannot be empty.")
            return
        }
         guard sourceLang.code != targetLang.code else {
             showAlert(title: "Invalid Selection", message: "Source and Target languages cannot be the same.")
             return
         }

        let command = "batch"
        // --- UPDATED arguments ---
        var args = [
            url.path,
            "--deck-name", deckName,
            "-s", sourceLang.code, // Add source language arg
            "-t", targetLang.code  // Add target language arg
        ]
        // --- END UPDATED ---
        if includeAudio { args.append("--audio") }
        if !includeGrammar { args.append("--no-grammar") }

        runGeneration(
            projectPath: settings.projectPath,
            command: command,
            args: args,
            isGenerating: $isGenerating,
            progressMessage: $progressMessage
        ) {
            // Optional: Cleanup security-scoped access after generation
             url.stopAccessingSecurityScopedResource()
        }
    }
}

struct CSVFileView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var fileURL: URL?
    @State private var deckName = "CSV Deck"
    @State private var csvColumn = "sentence"
    @State private var includeAudio = false
    @State private var includeGrammar = true

    // --- NEW Language States ---
    @State private var sourceLang: Language = supportedLanguages.first { $0.code == "fr" } ?? supportedLanguages[0]
    @State private var targetLang: Language = supportedLanguages.first { $0.code == "en" } ?? supportedLanguages[1]
    // --- END NEW ---

    @State private var isShowingFileImporter = false
    @State private var isGenerating = false
    @State private var progressMessage = ""

    var body: some View {
        VStack(spacing: 20) {
             Button(action: { isShowingFileImporter = true }) {
                HStack {
                   Image(systemName: fileURL == nil ? "doc.badge.plus" : "tablecells.fill")
                   Text(fileURL?.lastPathComponent ?? "Select a .csv file")
                }
                .padding()
                .frame(maxWidth: .infinity) // Make button wider
                .background(Color(.textBackgroundColor))
                .cornerRadius(8)
            }
            .buttonStyle(.plain) // Use plain style to allow background/cornerRadius
            .fileImporter(isPresented: $isShowingFileImporter, allowedContentTypes: [.commaSeparatedText]) { result in
                 if case .success(let url) = result {
                     _ = url.startAccessingSecurityScopedResource()
                     fileURL = url
                     // Auto-fill deck name
                     if deckName == "CSV Deck" {
                         deckName = url.deletingPathExtension().lastPathComponent.replacingOccurrences(of: "_", with: " ").capitalized
                     }
                 }
            }

            TextField("CSV Column Name (containing sentences)", text: $csvColumn)
                .textFieldStyle(RoundedBorderTextFieldStyle())

            DeckOptionsView(
                deckName: $deckName,
                includeAudio: $includeAudio,
                includeGrammar: $includeGrammar,
                // --- Pass language bindings ---
                sourceLang: $sourceLang,
                targetLang: $targetLang
                // --- End pass ---
            )

            GenerationView(onGenerate: generate, isGenerating: $isGenerating, progressMessage: $progressMessage)
            Spacer()
        }
        .padding()
    }

    func generate() {
        guard let url = fileURL else {
            showAlert(title: "Input Missing", message: "Please select a CSV file.")
            return
        }
        guard !csvColumn.isEmpty else {
            showAlert(title: "Input Missing", message: "CSV Column Name cannot be empty.")
            return
        }
        guard !deckName.isEmpty else {
            showAlert(title: "Input Missing", message: "Deck Name cannot be empty.")
            return
        }
        guard sourceLang.code != targetLang.code else {
             showAlert(title: "Invalid Selection", message: "Source and Target languages cannot be the same.")
             return
         }

        let command = "batch"
         // --- UPDATED arguments ---
        var args = [
            url.path,
            "--deck-name", deckName,
            "--column", csvColumn,
            "-s", sourceLang.code, // Add source language arg
            "-t", targetLang.code  // Add target language arg
        ]
        // --- END UPDATED ---
        if includeAudio { args.append("--audio") }
        if !includeGrammar { args.append("--no-grammar") }

        runGeneration(
            projectPath: settings.projectPath,
            command: command,
            args: args,
            isGenerating: $isGenerating,
            progressMessage: $progressMessage
        ) {
             url.stopAccessingSecurityScopedResource()
        }
    }
}

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Settings")
                .font(.largeTitle.weight(.thin))

            GroupBox("Python Project Location") {
                VStack(alignment: .leading) {
                    Text("Current Path:")
                        .font(.headline)
                    Text(settings.projectPath.isEmpty ? "Not set. Please select the 'learnit-anki' folder." : settings.projectPath)
                        .foregroundColor(.secondary)
                        .font(.callout)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .padding(.bottom, 5)

                    DirectoryPicker(path: $settings.projectPath)
                }
                .padding(5) // Padding inside the GroupBox
            }

            // --- NEW: Test Button ---
            GroupBox("Test Setup") {
                VStack(alignment: .leading) {
                   Text("Run Configuration Checks")
                       .font(.headline)
                   Text("Verify API keys, credentials, and dependencies.")
                      .foregroundColor(.secondary)
                      .font(.callout)
                      .padding(.bottom, 5)
                   Button(action: runTestCommand) {
                       Label("Run Test", systemImage: "stethoscope")
                   }
                }
                .padding(5)
            }
            // --- END NEW ---

            Spacer()
        }
        .padding()
    }

    // --- NEW: Function to run test command ---
    func runTestCommand() {
        let command = "test"
        let args: [String] = [] // Test command takes no arguments currently
        // Use temporary bindings for isGenerating and progressMessage, as they aren't needed long-term here
        var isGeneratingTemp = false
        var progressMessageTemp = ""

        runGeneration(
            projectPath: settings.projectPath,
            command: command,
            args: args,
            isGenerating: Binding<Bool>(get: { isGeneratingTemp }, set: { isGeneratingTemp = $0 }),
            progressMessage: Binding<String>(get: { progressMessageTemp }, set: { progressMessageTemp = $0 })
        ) {
             // Show result in alert - test output is designed for console, might need parsing for UI
             // showAlert(title: "Test Results", message: "Check the console output for details.")
             // The runGeneration completion handler already shows an alert based on success/failure
        }
    }
    // --- END NEW ---
}


// MARK: - Helper Views
struct DirectoryPicker: View {
    @Binding var path: String

    var body: some View {
        Button(action: selectDirectory) {
            Label("Select 'learnit-anki' Folder", systemImage: "folder.badge.plus")
        }
    }

    private func selectDirectory() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.message = "Please select the root folder of your 'learnit-anki' Python project." // More specific message

        if panel.runModal() == .OK {
            if let url = panel.url {
                // Basic validation: Check if key files/folders exist
                let venvPath = url.appendingPathComponent(".venv").path
                let scriptPath = url.appendingPathComponent("infrastructure/cli/main.py").path
                if FileManager.default.fileExists(atPath: venvPath) && FileManager.default.fileExists(atPath: scriptPath) {
                     self.path = url.path
                } else {
                     showAlert(title: "Incorrect Folder?", message: "The selected folder doesn't seem to contain the expected '.venv' directory or 'infrastructure/cli/main.py' script. Please ensure you select the correct 'learnit-anki' project root.")
                }
            }
        }
    }
}

// MARK: - Backend Logic

// --- UPDATED runGeneration function ---
func runGeneration(
    projectPath: String,
    command: String,
    args: [String],
    isGenerating: Binding<Bool>,
    progressMessage: Binding<String>,
    completion: (() -> Void)? = nil // Optional completion handler
) {
    // --- Basic Path Validation ---
    guard !projectPath.isEmpty else {
        showAlert(title: "Project Path Error", message: "Python project path is not set. Please set it in Settings.")
        return
    }
    let fileManager = FileManager.default
    guard fileManager.fileExists(atPath: projectPath) else {
         showAlert(title: "Project Path Error", message: "The specified project path does not exist:\n\(projectPath)")
         return
    }
    // --- End Validation ---


    isGenerating.wrappedValue = true
    progressMessage.wrappedValue = "Starting generation process..." // Updated message

    DispatchQueue.global(qos: .userInitiated).async {
        // --- Configuration ---
        // Find python within the .venv
        let pythonPath = "\(projectPath)/.venv/bin/python"
        let scriptPath = "\(projectPath)/infrastructure/cli/main.py"
        // --- End Configuration ---

        // Check if python/script exist before running
         guard fileManager.fileExists(atPath: pythonPath) else {
             DispatchQueue.main.async {
                isGenerating.wrappedValue = false
                showAlert(title: "Python Not Found", message: "Could not find the Python executable in the virtual environment at:\n\(pythonPath)\n\nDid you run 'poetry install' in the project directory?")
                completion?() // Call completion handler even on error
            }
            return
         }
         guard fileManager.fileExists(atPath: scriptPath) else {
             DispatchQueue.main.async {
                isGenerating.wrappedValue = false
                showAlert(title: "Script Not Found", message: "Could not find the Python script at:\n\(scriptPath)\n\nPlease check the project path in Settings.")
                completion?()
            }
            return
         }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env") // Use env to find python
        // Arguments: python executable, script path, command, followed by other args
        process.arguments = [pythonPath, scriptPath, command] + args
        process.currentDirectoryURL = URL(fileURLWithPath: projectPath) // Run from project root

        // Capture output/error
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        let outHandle = pipe.fileHandleForReading

        // Update progress message based on output (simple example)
        outHandle.readabilityHandler = { pipe in
            if let line = String(data: pipe.availableData, encoding: .utf8), !line.isEmpty {
                DispatchQueue.main.async {
                    // Update progress message - crude example, could parse better
                    if line.contains("Generating card") || line.contains("Processing") {
                       progressMessage.wrappedValue = line.trimmingCharacters(in: .whitespacesAndNewlines)
                    } else if line.contains("Successfully parsed") {
                       // Ignore verbose logs if needed
                    }
                    // Could add more parsing here for actual progress % if script provides it
                    print("PY_STDOUT: \(line.trimmingCharacters(in: .whitespacesAndNewlines))") // Log Python output to Xcode console
                }
            }
        }


        process.terminationHandler = { process in
            // Clean up readability handler
             outHandle.readabilityHandler = nil

            DispatchQueue.main.async {
                isGenerating.wrappedValue = false
                let outputData = outHandle.readDataToEndOfFile() // Read remaining data
                let output = String(data: outputData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                print("PY_FINAL_OUTPUT: \(output)") // Log final output
                 print("PY_EXIT_CODE: \(process.terminationStatus)") // Log exit code

                if process.terminationStatus == 0 {
                    // Try to find the output path in the final lines of output
                    let successLine = output.split(separator: "\n").last(where: { $0.contains("✅") && $0.contains(".apkg") })
                    let message = successLine != nil ? String(successLine!) : "Deck generated successfully.\nFind it in the 'output' folder."
                    showAlert(title: "Success!", message: message)
                } else {
                    // Try to find a specific error message
                    let errorLine = output.split(separator: "\n").last(where: { $0.contains("❌ Error:") })
                    let detail = errorLine != nil ? String(errorLine!) : "An error occurred."
                    showAlert(title: "Generation Failed", message: "\(detail)\n\nFull Output:\n\(output)")
                }
                completion?() // Call completion handler
            }
        }

        do {
            try process.run()
        } catch {
            DispatchQueue.main.async {
                isGenerating.wrappedValue = false
                showAlert(title: "Execution Error", message: "Could not launch the generation script: \(error.localizedDescription)")
                 completion?()
            }
        }
    }
}
// --- END UPDATED ---


func showAlert(title: String, message: String) {
    // Ensure alert runs on main thread
    DispatchQueue.main.async {
        let alert = NSAlert()
        alert.messageText = title
        alert.informativeText = message
        alert.alertStyle = (title.lowercased().contains("error") || title.lowercased().contains("failed")) ? .critical : .informational
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

// MARK: - Previews
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        // Provide a mock settings object for preview
        let settings = AppSettings()
        // settings.projectPath = "/Users/youruser/path/to/learnit-anki" // Optional: Set a path for preview
        return ContentView(settings: settings)
            .environmentObject(settings) // Ensure environment object is passed for preview
    }
}
