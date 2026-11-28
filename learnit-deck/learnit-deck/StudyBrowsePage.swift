import SwiftUI

struct StudyBrowsePage: View {
    @ObservedObject var library: StudyLibrary
    let decks: [StudyDeck]
    @State private var deck: Int64?
    @State private var query = ""
    @State private var unbracketed = false
    @State private var selected: Int64?
    @State private var results: [StudyCardSummary] = []
    @State private var loading = true
    @State private var issue: String?
    @State private var item: StudyCard?
    @State private var detailIssue: (id: Int64, message: String)?

    private struct Filter: Equatable {
        let query: String
        let deck: Int64?
        let unbracketed: Bool
        let revision: Int
    }

    private var filter: Filter {
        Filter(query: query, deck: deck, unbracketed: unbracketed, revision: library.revision)
    }

    init(library: StudyLibrary, decks: [StudyDeck], initialDeck: Int64?) {
        self.library = library
        self.decks = decks
        _deck = State(initialValue: initialDeck)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 5) {
                Text("Browse").font(.system(size: 34, weight: .semibold))
                Text("Find passages by Japanese text, reading, meaning, or source.").foregroundStyle(.secondary)
            }
            HSplitView {
                VStack(alignment: .leading, spacing: 10) {
                    TextField("Search cards", text: $query)
                        .textFieldStyle(.roundedBorder)
                        .accessibilityLabel("Search cards")
                    Picker("Deck", selection: $deck) {
                        Text("All decks").tag(nil as Int64?)
                        ForEach(decks) { Text($0.name).tag(Optional($0.id)) }
                    }
                    Toggle("Unbracketed readings", isOn: $unbracketed)
                    if let issue {
                        Text(issue).foregroundStyle(.secondary)
                    }
                    if loading && results.isEmpty {
                        ProgressView().controlSize(.small)
                    }
                    if !loading && results.isEmpty && issue == nil {
                        Text("No cards found.").foregroundStyle(.secondary).padding(.vertical, 8)
                    }
                    if !loading && !results.isEmpty && issue == nil {
                        Text(results.count == 1 ? "1 card" : "\(results.count.formatted()) cards")
                            .font(.caption).foregroundStyle(.secondary).monospacedDigit()
                    }
                    List(selection: $selected) {
                        ForEach(results) { card in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(card.expression).lineLimit(2)
                                Text("\(decks.first { $0.id == card.deckId }?.name ?? "Deck") · \(card.state.capitalized)")
                                    .font(.caption).foregroundStyle(.secondary)
                            }.padding(.vertical, 3).tag(card.id)
                        }
                    }
                }
                .padding(.trailing, 12)
                .frame(minWidth: 225, idealWidth: 275)

                inspector
                    .padding(.leading, 12)
                    .frame(minWidth: 345, maxWidth: .infinity)
            }
        }
        .padding(26)
        .background(Color(nsColor: .windowBackgroundColor))
        .task(id: filter) {
            try? await Task.sleep(for: .milliseconds(150))
            if !Task.isCancelled { await search() }
        }
        .task(id: selected) { await inspect(selected) }
    }

    @ViewBuilder
    private var inspector: some View {
        let failure = detailIssue.flatMap { $0.id == selected ? $0.message : nil }
        if let item {
            let selectionReady = item.id == selected
            VStack(alignment: .leading, spacing: 8) {
                if let failure, let selected {
                    HStack {
                        Text(failure).font(.caption).foregroundStyle(.secondary)
                        Button("Retry") { Task { await inspect(selected) } }
                    }
                }
                StudyCardInspector(card: item, decks: decks, selectionReady: selectionReady,
                                   loading: selected != nil && !selectionReady && failure == nil) { changes, target in
                    try await save(item, changes: changes, target: target)
                }
                .allowsHitTesting(selectionReady)
            }
        } else if let selected {
            if let failure {
                VStack(spacing: 10) {
                    Text(failure).foregroundStyle(.secondary)
                    Button("Retry") { Task { await inspect(selected) } }
                }.frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ProgressView("Loading card…").frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        } else {
            ContentUnavailableView("Select a card", systemImage: "text.rectangle")
        }
    }

    private func save(_ card: StudyCard, changes: StudyCardChanges, target: Int64) async throws {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false,
                                                attributes: [.posixPermissions: 0o700])
        defer { try? FileManager.default.removeItem(at: folder) }
        let draft = folder.appendingPathComponent("changes.json")
        try JSONEncoder().encode(changes).write(to: draft)
        let saved = try await library.request(StudyCard.self, [
            "edit", String(card.id), String(card.revision), String(target), draft.path,
        ])
        if selected == saved.id { item = saved }
        await library.collectionChanged()
    }

    private func search() async {
        let requested = filter
        loading = true
        issue = nil
        defer {
            if requested == filter { loading = false }
        }
        do {
            var command = ["browse", "--all"]
            if let deck { command += ["--deck", String(deck)] }
            if unbracketed { command.append("--unbracketed") }
            let response = try await library.request(StudyBrowseResult.self, command + ["--", query])
            guard !Task.isCancelled, requested == filter else { return }
            results = response.cards
            if !results.contains(where: { $0.id == selected }) { selected = results.first?.id }
        } catch {
            if !Task.isCancelled && requested == filter { issue = error.localizedDescription }
        }
    }

    private func inspect(_ id: Int64?) async {
        guard !Task.isCancelled, id == selected else { return }
        detailIssue = nil
        guard let id else { item = nil; return }
        do {
            let candidate = try await library.request(StudyCard.self, ["card", String(id)])
            if !Task.isCancelled && selected == id { item = candidate }
        } catch {
            if !Task.isCancelled && selected == id { detailIssue = (id, error.localizedDescription) }
        }
    }
}

private struct StudyCardInspector: View {
    let card: StudyCard
    let decks: [StudyDeck]
    let selectionReady: Bool
    let loading: Bool
    let commit: (StudyCardChanges, Int64) async throws -> Void
    @State private var fields: StudyCardChanges
    @State private var deck: Int64
    @State private var saving = false
    @State private var status = ""
    @State private var editingID: Int64

    init(card: StudyCard, decks: [StudyDeck], selectionReady: Bool, loading: Bool,
         commit: @escaping (StudyCardChanges, Int64) async throws -> Void) {
        self.card = card
        self.decks = decks
        self.selectionReady = selectionReady
        self.loading = loading
        self.commit = commit
        _fields = State(initialValue: StudyCardChanges(card))
        _deck = State(initialValue: card.deckId)
        _editingID = State(initialValue: card.id)
    }

    var body: some View {
        ScrollViewReader { scroll in
            ScrollView {
                VStack(alignment: .leading, spacing: 13) {
                    HStack {
                        Text("Card details").font(.headline)
                        Spacer()
                        if loading {
                            ProgressView().controlSize(.small).accessibilityLabel("Loading card")
                        } else if let due = card.due {
                            Text(Date(timeIntervalSince1970: due).formatted(date: .abbreviated, time: .shortened))
                                .foregroundStyle(.secondary)
                        } else {
                            Text(card.state.capitalized).foregroundStyle(.secondary)
                        }
                    }.id("card-top")
                    Picker("Deck", selection: $deck) {
                        ForEach(decks) { Text($0.name).tag($0.id) }
                    }
                    field("Japanese passage", $fields.expression, height: 105)
                    TextField("Dictionary links", text: $fields.headwords)
                        .textFieldStyle(.roundedBorder)
                    let words = JapaneseDictionary.words(in: fields.headwords)
                    if !words.isEmpty {
                        DictionaryWordLinks(words: words)
                    }
                    field("Meaning and context", $fields.meaning, height: 175)
                    field("Reading", $fields.reading, height: 90)
                    HStack {
                        if !status.isEmpty { Text(status).foregroundStyle(.secondary) }
                        Spacer()
                        Button(saving ? "Saving…" : "Save changes") {
                            let id = card.id
                            let changes = fields
                            let target = deck
                            saving = true
                            Task {
                                defer { if editingID == id { saving = false } }
                                do {
                                    try await commit(changes, target)
                                    if editingID == id { status = "Saved." }
                                } catch {
                                    if editingID == id { status = error.localizedDescription }
                                }
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!selectionReady || saving || fields.expression.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }.padding(10)
            }
            .onChange(of: card.id) {
                editingID = card.id
                fields = StudyCardChanges(card)
                deck = card.deckId
                status = ""
                saving = false
                scroll.scrollTo("card-top", anchor: .top)
            }
        }
    }

    private func field(_ title: String, _ binding: Binding<String>, height: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.subheadline.weight(.medium))
            TextEditor(text: binding)
                .accessibilityLabel(title)
                .padding(5)
                .frame(height: height)
                .overlay { RoundedRectangle(cornerRadius: 6).strokeBorder(.separator).allowsHitTesting(false) }
        }
    }
}
