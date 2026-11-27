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
