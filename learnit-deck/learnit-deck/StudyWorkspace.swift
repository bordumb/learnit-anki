import SwiftUI
import UniformTypeIdentifiers

enum StudyPage: String, CaseIterable, Identifiable {
    case today = "Today"
    case review = "Review"
    case create = "Create"
    case decks = "Decks"
    case browse = "Browse"
    case progress = "Progress"
    case settings = "Settings"

    var id: Self { self }

    var icon: String {
        switch self {
        case .today: "sun.max"
        case .review: "play.rectangle"
        case .create: "square.and.pencil"
        case .decks: "rectangle.stack"
        case .browse: "magnifyingglass"
        case .progress: "chart.bar.xaxis"
        case .settings: "gearshape"
        }
    }
}

struct StudyWorkspace: View {
    @StateObject private var library: StudyLibrary
    @State private var selected: StudyPage? = .today
    @State private var reviewDeck: Int64?
    @State private var browseDeck: Int64?
    @State private var createDeck: Int64?
    @State private var session = UUID()
    @State private var deckRequest = false
    @State private var importFile: StudyImportFile?
    @State private var readingCleanup: StudyReadingCleanup?
    @State private var cleanupBackup: URL?
    @State private var restoreFile: URL?
    @State private var confirmingRestore = false
    @State private var working: String?
    @State private var message: String?

    init(project: String, database: URL? = nil) {
        _library = StateObject(wrappedValue: StudyLibrary(project: project, database: database))
    }

    var body: some View {
        NavigationSplitView {
            List(selection: $selected) {
                ForEach(StudyPage.allCases) { page in
                    Label(page.rawValue, systemImage: page.icon).tag(page)
                }
            }
            .listStyle(.sidebar)
            .safeAreaInset(edge: .top) {
                Label("Learnit", systemImage: "book.closed.fill")
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 18).padding(.vertical, 13)
            }
            .navigationSplitViewColumnWidth(min: 155, ideal: 181, max: 230)
        } detail: {
            Group {
                if !library.ready {
                    if library.problem == nil {
                        ProgressView("Opening your collection…").frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else {
                        ContentUnavailableView {
                            Label("Could not open the collection", systemImage: "externaldrive.badge.exclamationmark")
                        } description: {
                            Text(library.problem ?? "")
                        } actions: {
                            Button("Try again") { Task { library.problem = nil; await library.load() } }
                        }
                    }
                } else {
                    ZStack {
                        if selected != .create { detail }
                        MediaCardView(library: library, decks: library.summary.decks, initialDeck: createDeck,
                                      active: selected == .create, createDeck: { deckRequest = true })
                            .opacity(selected == .create ? 1 : 0)
                            .allowsHitTesting(selected == .create)
                            .accessibilityHidden(selected != .create)
                    }
                }
            }
            .navigationTitle((selected ?? .today).rawValue)
            .toolbar {
                if selected != .create && library.ready {
                    ToolbarItem(placement: .primaryAction) {
                        Button("New card", systemImage: "plus") { openCreate() }
                            .disabled(working != nil)
                    }
                }
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                if let working {
                    HStack { ProgressView().controlSize(.small); Text(working); Spacer() }
                        .padding(12).background(.regularMaterial)
                } else if let message {
                    HStack {
                        Text(message)
                        Spacer()
                        Button("Dismiss", systemImage: "xmark") { self.message = nil }
                            .labelStyle(.iconOnly).buttonStyle(.plain)
                    }
                    .padding(12).background(.regularMaterial)
                }
            }
        }
        .tint(Color(red: 0.37, green: 0.30, blue: 0.72))
        .task(id: selected) { await library.load() }
        .frame(minWidth: 940, minHeight: 590)
        .alert("Learnit", isPresented: Binding(
            get: { library.ready && library.problem != nil },
            set: { if !$0 { library.problem = nil } }
        )) {
            Button("OK", role: .cancel) { library.problem = nil }
        } message: {
            Text(library.problem ?? "")
        }
        .alert("Replace this collection?", isPresented: $confirmingRestore) {
            Button("Cancel", role: .cancel) { restoreFile = nil }
            Button("Restore backup", role: .destructive) {
                if let file = restoreFile { restore(file) }
                restoreFile = nil
            }
        } message: {
            Text("The backup will replace the current cards, reviews, and media.")
        }
        .sheet(isPresented: $deckRequest) {
            NewStudyDeck { name, description in
                let deck = try await library.request(StudyCardID.self, ["create-deck", "--", name, description])
                await library.collectionChanged()
                return deck.id
            } onCreated: { id in
                if selected == .create { createDeck = id }
            }
        }
        .sheet(item: $importFile) { file in
            importPreview(file)
        }
        .sheet(item: $readingCleanup) { report in
            cleanupPreview(report)
        }
    }

    @ViewBuilder
    private var detail: some View {
        switch selected ?? .today {
        case .today:
            today
        case .review:
            StudyReviewPage(library: library, deck: reviewDeck) { selected = .today }
                .id(session)
        case .create:
            EmptyView()
        case .decks:
            StudyDecksPage(summary: library.summary, create: { deckRequest = true }, study: startReview, browse: openBrowse)
        case .browse:
            StudyBrowsePage(library: library, decks: library.summary.decks, initialDeck: browseDeck)
        case .progress:
            StudyProgressPage(summary: library.summary)
        case .settings:
            settings
        }
    }

    private var today: some View {
        StudyPageLayout("Today", subtitle: "Pick up where you left off in your collection.") {
            if library.summary.decks.isEmpty {
                StudyPanel {
                    VStack(alignment: .leading, spacing: 13) {
                        Text("Bring over your Japanese deck").font(.title2.weight(.semibold))
                        Text("Import your passages, readings, and review history to start studying here.")
                            .foregroundStyle(.secondary)
                        HStack {
                            Button("Import from Anki", action: chooseImport).buttonStyle(.borderedProminent)
                            Button("New deck") { deckRequest = true }
                        }
                    }
                }
            } else {
                StudyPanel(tinted: true) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(library.summary.due == 0 ? "You’re caught up" : "\(library.summary.due.formatted()) cards to review")
                            .font(.system(size: 28, weight: .semibold))
                        Text(library.summary.fresh == 0 ? "Revisit the passages that are ready." : "Review due passages and pick up new ones.")
                            .foregroundStyle(.secondary)
                        Button("Start review", systemImage: "play.fill") { startReview(nil) }
                            .buttonStyle(.borderedProminent)
                    }
                }
            }
            HStack(spacing: 12) {
                StudyStat("Due now", value: library.summary.due)
                StudyStat("New cards", value: library.summary.fresh)
                StudyStat("Reviewed today", value: library.summary.reviewed)
            }
            if !library.summary.decks.isEmpty {
                StudyPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("Your decks").font(.headline)
                            Spacer()
                            Button("Import from Anki", action: chooseImport)
                        }
                        ForEach(library.summary.decks) { deck in
                            Divider()
                            HStack {
                                Text(deck.name).font(.body.weight(.medium))
                                Spacer()
                                Text("\(deck.due.formatted()) due · \(deck.fresh.formatted()) new")
                                    .foregroundStyle(.secondary).monospacedDigit()
                                Button("Study") { startReview(deck.id) }
                            }
                        }
                    }
                }
            }
        }
    }

    private var settings: some View {
        StudyPageLayout("Settings", subtitle: "Manage your collection and review preferences.") {
            HStack(alignment: .top, spacing: 16) {
                StudyPanel {
                    VStack(alignment: .leading, spacing: 13) {
                        Text("Collection").font(.headline)
                        Button("Import from Anki…", action: chooseImport)
                        Button("Back up collection…", action: chooseBackup)
                        Button("Restore a backup…", action: chooseRestore)
                        Button("Clean up older readings…", action: previewReadingCleanup)
                        if let cleanupBackup {
                            Button("Show reading cleanup backup") {
                                NSWorkspace.shared.activateFileViewerSelecting([cleanupBackup])
                            }.buttonStyle(.link)
                        }
                        Text(library.database.path).textSelection(.enabled)
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    .disabled(working != nil)
                }
                StudyPanel {
                    StudyPreferencesEditor(preferences: library.summary.preferences) { limit, audio in
                        let _ = try await library.request(StudyPreferences.self, [
                            "preferences", audio ? "--auto-audio" : "--no-auto-audio", String(limit),
                        ])
                        await library.collectionChanged()
                    }
                }
            }
        }
    }

    private func startReview(_ id: Int64?) {
        reviewDeck = id
        session = UUID()
        selected = .review
    }

    private func previewReadingCleanup() {
        working = "Checking older readings…"
        Task {
            defer { working = nil }
            do {
                readingCleanup = try await library.request(StudyReadingCleanup.self, ["preview-reading-cleanup"])
            } catch { library.problem = error.localizedDescription }
        }
    }

    private func cleanupPreview(_ report: StudyReadingCleanup) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Clean up older readings").font(.title2.weight(.semibold))
            HStack(spacing: 12) {
                StudyStat("Ready to convert", value: report.convertible)
                StudyStat("Need manual review", value: report.needsReview)
            }
            if report.noKanji > 0 {
                Text("\(report.noKanji.formatted()) passages have no kanji to annotate.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if !report.examples.isEmpty {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach(report.examples) { example in
                            VStack(alignment: .leading, spacing: 5) {
                                Text(example.before).foregroundStyle(.secondary)
                                Text(example.after).font(.body.weight(.medium))
                            }
                            .textSelection(.enabled)
                            Divider()
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(maxHeight: 255)
            }
            Text("Learnit backs up the collection before applying these changes.")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Button("Close") { readingCleanup = nil }.keyboardShortcut(.cancelAction)
                Button("Convert \(report.convertible.formatted()) readings") { applyReadingCleanup(report) }
                    .buttonStyle(.borderedProminent)
                    .disabled(report.convertible == 0)
            }
        }
        .padding(24).frame(width: 590)
    }

    private func applyReadingCleanup(_ report: StudyReadingCleanup) {
        readingCleanup = nil
        working = "Converting older readings…"
        Task {
            defer { working = nil }
            do {
                let result = try await library.request(StudyReadingCleanupResult.self,
                                                       ["apply-reading-cleanup", report.token])
                cleanupBackup = result.backup.map { URL(fileURLWithPath: $0) }
                await library.collectionChanged()
                message = "Converted \(result.updated.formatted()) readings. \(result.needsReview.formatted()) need manual review."
            } catch { library.problem = error.localizedDescription }
        }
    }

    private func openCreate() {
        createDeck = nil
        selected = .create
    }

    private func openBrowse(_ id: Int64?) {
        browseDeck = id
        selected = .browse
    }

    private func chooseImport() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [UTType(filenameExtension: "apkg") ?? .data]
        panel.allowsMultipleSelection = false
        let example = URL(fileURLWithPath: library.project).appendingPathComponent("output/nihongo-deck-repaired.apkg")
        if FileManager.default.fileExists(atPath: example.path) {
            panel.directoryURL = example.deletingLastPathComponent()
        }
        guard panel.runModal() == .OK, let file = panel.url else { return }
        working = "Reading Anki package…"
        Task {
            defer { working = nil }
            do {
                let details = try await library.request(StudyImport.self, ["preview-import", "--", file.path], accessing: file)
                importFile = StudyImportFile(url: file, details: details)
            } catch { library.problem = error.localizedDescription }
        }
    }

    private func importPreview(_ file: StudyImportFile) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Preview Anki import").font(.title2.weight(.semibold))
            Text(file.url.lastPathComponent).foregroundStyle(.secondary)
            ForEach(file.details.decks, id: \.self) { Text($0).font(.headline) }
            HStack(spacing: 12) {
                StudyStat("Cards", value: file.details.cards)
                StudyStat("Review records", value: file.details.reviews)
                StudyStat("Media files", value: file.details.media)
            }
            if file.details.skipped > 0 {
                Text("\(file.details.skipped.formatted()) cards use unsupported templates or note fields.")
                    .foregroundStyle(.secondary)
            }
            HStack {
                Spacer()
                Button("Cancel") { importFile = nil }.keyboardShortcut(.cancelAction)
                Button("Import collection") {
                    importFile = nil
                    working = "Importing passages and review history…"
                    Task {
                        defer { working = nil }
                        do {
                            let result = try await library.request(StudyImport.self, ["import", "--", file.url.path], accessing: file.url)
                            await library.collectionChanged()
                            message = "Added \((result.added ?? 0).formatted()) cards."
                        } catch { library.problem = error.localizedDescription }
                    }
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
                .disabled(file.details.cards == 0)
            }
        }
        .padding(24).frame(width: 530)
    }

    private func chooseBackup() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "Learnit Backup.sqlite3"
        guard panel.runModal() == .OK, let file = panel.url else { return }
        working = "Backing up the collection…"
        Task {
            defer { working = nil }
            do {
                let _ = try await library.request(StudyBackup.self, ["backup", "--", file.path], accessing: file)
                message = "Backup saved to \(file.lastPathComponent)."
            } catch { library.problem = error.localizedDescription }
        }
    }

    private func chooseRestore() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let file = panel.url else { return }
        restoreFile = file
        confirmingRestore = true
    }

    private func restore(_ file: URL) {
        working = "Restoring the collection…"
        Task {
            defer { working = nil }
            do {
                let _ = try await library.request(StudySummary.self, ["restore", "--", file.path], accessing: file)
                await library.collectionChanged()
                reviewDeck = nil
                browseDeck = nil
                createDeck = nil
                selected = .today
                message = "Collection restored."
            } catch { library.problem = error.localizedDescription }
        }
    }
}

private struct StudyImportFile: Identifiable {
    var id: URL { url }
    let url: URL
    let details: StudyImport
}

struct StudyPageLayout<Content: View>: View {
    let title: String
    let subtitle: String
    private let content: Content

    init(_ title: String, subtitle: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.subtitle = subtitle
        self.content = content()
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 19) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(title).font(.system(size: 34, weight: .semibold))
                    Text(subtitle).foregroundStyle(.secondary)
                }
                content
            }
            .padding(29)
            .frame(maxWidth: 1030, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

struct StudyPanel<Content: View>: View {
    var tinted = false
    @ViewBuilder var content: () -> Content

    var body: some View {
        content()
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(18)
            .background(tinted ? Color.accentColor.opacity(0.10) : Color(nsColor: .controlBackgroundColor),
                        in: RoundedRectangle(cornerRadius: 12))
            .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(Color(nsColor: .separatorColor).opacity(0.28)) }
    }
}

struct StudyStat: View {
    let title: String
    let value: Int

    init(_ title: String, value: Int) { self.title = title; self.value = value }

    var body: some View {
        StudyPanel {
            VStack(alignment: .leading, spacing: 5) {
                Text(title).foregroundStyle(.secondary)
                Text(value.formatted()).font(.title.weight(.semibold)).monospacedDigit()
            }
            .accessibilityElement(children: .combine)
        }
    }
}

private struct NewStudyDeck: View {
    let create: (String, String) async throws -> Int64
    let onCreated: (Int64) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var description = ""
    @State private var issue = ""
    @State private var saving = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("New deck").font(.title2.weight(.semibold))
            TextField("Name", text: $name)
            TextField("Description", text: $description, axis: .vertical)
            if !issue.isEmpty { Text(issue).foregroundStyle(.secondary) }
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction).disabled(saving)
                Button("Create deck") {
                    saving = true
                    Task {
                        defer { saving = false }
                        do {
                            onCreated(try await create(name, description))
                            dismiss()
                        } catch { issue = error.localizedDescription }
                    }
                }.buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
                    .disabled(saving || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .textFieldStyle(.roundedBorder)
        .padding(24).frame(width: 410)
        .interactiveDismissDisabled(saving)
    }
}

private struct StudyPreferencesEditor: View {
    let save: (Int, Bool) async throws -> Void
    @State private var limit: Int
    @State private var audio: Bool
    @State private var saving = false
    @State private var status = ""

    init(preferences: StudyPreferences, save: @escaping (Int, Bool) async throws -> Void) {
        _limit = State(initialValue: preferences.newLimit)
        _audio = State(initialValue: preferences.autoAudio != 0)
        self.save = save
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            Text("Study preferences").font(.headline)
            Stepper("New cards per day · \(limit)", value: $limit, in: 0...999)
            Toggle("Play audio after revealing the answer", isOn: $audio)
            Button(saving ? "Saving…" : "Save preferences") {
                saving = true
                Task {
                    defer { saving = false }
                    do { try await save(limit, audio); status = "Preferences saved." }
                    catch { status = error.localizedDescription }
                }
            }.disabled(saving)
            if !status.isEmpty { Text(status).foregroundStyle(.secondary).font(.caption) }
        }
    }
}
