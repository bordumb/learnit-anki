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
                    
                SettingsView()
                    .tabItem { Label("Settings", systemImage: "gear") }
                    .tag(3)
            }
            .padding()
        }
        .frame(minWidth: 500, idealWidth: 600, maxWidth: 800, minHeight: 450, idealHeight: 550, maxHeight: 650)
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

struct DeckOptionsView: View {
    @Binding var deckName: String
    @Binding var includeAudio: Bool
    @Binding var includeGrammar: Bool
    
    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("Deck Options")
                .font(.headline)
                .foregroundColor(.secondary)
            
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
                ProgressView().progressViewStyle(LinearProgressViewStyle())
                Text(progressMessage)
                    .foregroundColor(.secondary)
                    .font(.caption)
            } else {
                Button(action: onGenerate) {
                    Label("Generate Deck", systemImage: "play.fill")
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding()
    }
}

// MARK: - Tab Views
struct SingleSentenceView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var sentence = ""
    @State private var deckName = "French Practice"
    @State private var includeAudio = false
    @State private var includeGrammar = true
    @State private var isGenerating = false
    @State private var progressMessage = ""
    
    var body: some View {
        VStack(spacing: 20) {
            TextField("Enter French sentence here...", text: $sentence)
                .textFieldStyle(RoundedBorderTextFieldStyle()).font(.title3)
            DeckOptionsView(deckName: $deckName, includeAudio: $includeAudio, includeGrammar: $includeGrammar)
            GenerationView(onGenerate: generate, isGenerating: $isGenerating, progressMessage: $progressMessage)
            Spacer()
        }
        .padding()
    }
    
    func generate() {
        guard !sentence.isEmpty else {
            showAlert(title: "Error", message: "Sentence cannot be empty.")
            return
        }
        
        let command = "add"
        var args = [sentence, "--deck-name", deckName]
        if includeAudio { args.append("--audio") }
        if !includeGrammar { args.append("--no-grammar") }
        
        runGeneration(projectPath: settings.projectPath, command: command, args: args, isGenerating: $isGenerating, progressMessage: $progressMessage)
    }
}

struct TextFileView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var fileURL: URL?
    @State private var deckName = "Text File Deck"
    @State private var includeAudio = false
    @State private var includeGrammar = true
    @State private var isShowingFileImporter = false
    @State private var isGenerating = false
    @State private var progressMessage = ""
    
    var body: some View {
        VStack(spacing: 20) {
            Button(action: { isShowingFileImporter = true }) {
                if let url = fileURL {
                    Label(url.lastPathComponent, systemImage: "doc.text.fill")
                } else {
                    Label("Select a .txt file", systemImage: "doc.badge.plus")
                }
            }
            .fileImporter(isPresented: $isShowingFileImporter, allowedContentTypes: [.plainText]) { result in
                if case .success(let url) = result { fileURL = url }
            }
            DeckOptionsView(deckName: $deckName, includeAudio: $includeAudio, includeGrammar: $includeGrammar)
            GenerationView(onGenerate: generate, isGenerating: $isGenerating, progressMessage: $progressMessage)
            Spacer()
        }
        .padding()
    }
    
    func generate() {
        guard let url = fileURL else {
            showAlert(title: "Error", message: "Please select a text file.")
            return
        }
        
        let command = "batch"
        var args = [url.path, "--deck-name", deckName]
        if includeAudio { args.append("--audio") }
        if !includeGrammar { args.append("--no-grammar") }
        
        runGeneration(projectPath: settings.projectPath, command: command, args: args, isGenerating: $isGenerating, progressMessage: $progressMessage)
    }
}

struct CSVFileView: View {
    @EnvironmentObject var settings: AppSettings
    @State private var fileURL: URL?
    @State private var deckName = "CSV Deck"
    @State private var csvColumn = "sentence"
    @State private var includeAudio = false
    @State private var includeGrammar = true
    @State private var isShowingFileImporter = false
    @State private var isGenerating = false
    @State private var progressMessage = ""
    
    var body: some View {
        VStack(spacing: 20) {
            Button(action: { isShowingFileImporter = true }) {
                if let url = fileURL {
                    Label(url.lastPathComponent, systemImage: "tablecells.fill")
                } else {
                    Label("Select a .csv file", systemImage: "doc.badge.plus")
                }
            }
            .fileImporter(isPresented: $isShowingFileImporter, allowedContentTypes: [.commaSeparatedText]) { result in
                if case .success(let url) = result { fileURL = url }
            }
            TextField("CSV Column Name", text: $csvColumn).textFieldStyle(RoundedBorderTextFieldStyle())
            DeckOptionsView(deckName: $deckName, includeAudio: $includeAudio, includeGrammar: $includeGrammar)
            GenerationView(onGenerate: generate, isGenerating: $isGenerating, progressMessage: $progressMessage)
            Spacer()
        }
        .padding()
    }
    
    func generate() {
        guard let url = fileURL else {
            showAlert(title: "Error", message: "Please select a CSV file.")
            return
        }
        
        let command = "batch"
        var args = [url.path, "--deck-name", deckName, "--column", csvColumn]
        if includeAudio { args.append("--audio") }
        if !includeGrammar { args.append("--no-grammar") }
        
        runGeneration(projectPath: settings.projectPath, command: command, args: args, isGenerating: $isGenerating, progressMessage: $progressMessage)
    }
}

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Settings")
                .font(.largeTitle.weight(.thin))
            
            VStack(alignment: .leading) {
                Text("Python Project Path")
                    .font(.headline)
                Text(settings.projectPath.isEmpty ? "Not set" : settings.projectPath)
                    .foregroundColor(.secondary)
                    .font(.callout)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
            
            DirectoryPicker(path: $settings.projectPath)
            
            Spacer()
        }
        .padding()
    }
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
        
        if panel.runModal() == .OK {
            if let url = panel.url {
                self.path = url.path
            }
        }
    }
}

// MARK: - Backend Logic
func runGeneration(projectPath: String, command: String, args: [String], isGenerating: Binding<Bool>, progressMessage: Binding<String>) {
    isGenerating.wrappedValue = true
    progressMessage.wrappedValue = "Starting generation..."
    
    DispatchQueue.global(qos: .userInitiated).async {
        // --- Configuration ---
        // The path is now dynamic, taken from the AppSettings.
        let pythonPath = "\(projectPath)/.venv/bin/python"
        let scriptPath = "\(projectPath)/infrastructure/cli/main.py"
        // --- End Configuration ---
        
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = [pythonPath, scriptPath, command] + args
        process.currentDirectoryURL = URL(fileURLWithPath: projectPath)
        
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        
        process.terminationHandler = { process in
            DispatchQueue.main.async {
                isGenerating.wrappedValue = false
                let outputData = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: outputData, encoding: .utf8) ?? ""
                
                if process.terminationStatus == 0 {
                    showAlert(title: "Success!", message: "Deck generated successfully.\n\nFind it in the 'output' folder of your project.")
                } else {
                    showAlert(title: "Generation Failed", message: "An error occurred.\n\nDetails:\n\(output)")
                }
            }
        }
        
        do {
            // Check if the script path is valid before running
            let fileManager = FileManager.default
            guard fileManager.fileExists(atPath: scriptPath) else {
                 DispatchQueue.main.async {
                    isGenerating.wrappedValue = false
                    showAlert(title: "Script Not Found", message: "Could not find the Python script at:\n\(scriptPath)\n\nPlease check the project path in Settings.")
                }
                return
            }
            
            try process.run()
        } catch {
            DispatchQueue.main.async {
                isGenerating.wrappedValue = false
                showAlert(title: "Execution Error", message: "Could not run the generation script: \(error.localizedDescription)")
            }
        }
    }
}

func showAlert(title: String, message: String) {
    let alert = NSAlert()
    alert.messageText = title
    alert.informativeText = message
    alert.alertStyle = .warning
    alert.addButton(withTitle: "OK")
    alert.runModal()
}

// MARK: - Previews
struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView(settings: AppSettings())
    }
}

