import SwiftUI

struct PassageDraft: Encodable, Sendable {
    let expression: String
    let definitions: String
    let source: String
    let context: String
    let translation: String
    var reading = ""
    var headwords = ""

    static func clean(_ text: String) -> String {
        text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var meaning: [String] {
        [definitions, source, context, translation].map(Self.clean).filter { !$0.isEmpty }
    }

    var isReady: Bool {
        !Self.clean(expression).isEmpty
            && (!dictionaryLinks.isEmpty || [definitions, context, translation].contains { !Self.clean($0).isEmpty })
    }

    var dictionaryLinks: [String] {
        JapaneseDictionary.words(in: headwords)
    }
}

struct PassagePreview: View {
    let deckName: String
    let draft: PassageDraft
    let audioLabels: [String]
    let exportIssue: String?
    let commitTitle: String
    let project: String
    @Binding var furigana: FuriganaDraft?
    let export: (PassageDraft) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var attempt = 0

    private var passage: String {
        PassageDraft.clean(draft.expression)
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")
    }

    var body: some View {
        VStack(spacing: 0) {
            Text("Card preview")
                .font(.title2.weight(.semibold))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(24)
            Divider()
            HStack(alignment: .top, spacing: 0) {
                side("Front") {
                    expression
                }
                Divider()
                side("Back") {
                    Text("Furigana").font(.subheadline.weight(.semibold))
                    readingPreview
                    Divider()
                    if !draft.dictionaryLinks.isEmpty {
                        DictionaryWordLinks(words: draft.dictionaryLinks)
                    }
                    ForEach(Array(draft.meaning.enumerated()), id: \.offset) { _, block in
                        Text(block).fixedSize(horizontal: false, vertical: true)
                    }
                    ForEach(audioLabels, id: \.self) { label in
                        Label(label, systemImage: "speaker.wave.2")
                            .foregroundStyle(.secondary)
                    }
                }
                .frame(maxWidth: .infinity)
            }
            Divider()
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(deckName).foregroundStyle(.secondary)
                    if let exportIssue { Text(exportIssue).font(.caption).foregroundStyle(.secondary) }
                }
                Spacer()
                Button("Back to draft") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(commitTitle) {
                    var approved = draft
                    approved.reading = furigana?.ankiReading ?? ""
                    dismiss()
                    export(approved)
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
                .disabled(exportIssue != nil || furigana?.source != passage)
            }
            .padding(18)
        }
        .frame(minWidth: 700, idealWidth: 850, minHeight: 390, idealHeight: 520)
        .task(id: attempt) {
            guard furigana?.source != passage || attempt > 0 else { return }
            let result = await FuriganaDraft.generate(for: passage, project: project)
            if !Task.isCancelled { furigana = result }
        }
    }

    private var expression: some View {
        Text(passage)
            .font(.system(.title3, design: .serif))
            .fixedSize(horizontal: false, vertical: true)
    }

    @ViewBuilder
    private var readingPreview: some View {
        if let reading = Binding($furigana), reading.wrappedValue.source == passage {
            if let error = reading.wrappedValue.generationError {
                Text(error).font(.caption).foregroundStyle(.secondary)
                if reading.wrappedValue.ankiReading.isEmpty {
                    Button("Retry furigana") {
                        furigana = nil
                        attempt += 1
                    }
                }
            }
            if reading.wrappedValue.spans.contains(where: \.editable) {
                Text("Select a word to correct or add its reading.").font(.caption).foregroundStyle(.secondary)
                FuriganaEditor(draft: reading)
            } else {
                expression
            }
        } else {
            ProgressView("Generating furigana…").controlSize(.small)
            expression
        }
    }

    private func side<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text(title).font(.headline).foregroundStyle(.secondary)
                content()
            }
            .textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(24)
        }
    }
}
