//
//  learnit_deckApp.swift
//  learnit-deck
//
//  Created by bordumb on 20/10/2025.
//

import SwiftUI
import UniformTypeIdentifiers

// MARK: - Main Application
@main
struct AnkiGeneratorApp: App {
    @StateObject private var settings = AppSettings()

    var body: some Scene {
        WindowGroup {
            // Show a welcome/setup screen if the path isn't set.
            // Otherwise, show the main app content.
            if settings.projectPath.isEmpty {
                WelcomeView(settings: settings)
            } else {
                ContentView(settings: settings)
            }
        }
        .windowStyle(HiddenTitleBarWindowStyle())
    }
}
