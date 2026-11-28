import CoreServices
import Foundation
import SwiftUI

enum JapaneseDictionary {
    static func definition(for word: String) -> String? {
        let range = CFRange(location: 0, length: word.utf16.count)
        guard let result = DCSCopyTextDefinition(nil, word as CFString, range)?.takeRetainedValue() else { return nil }
        let entry = (result as String).trimmingCharacters(in: .whitespacesAndNewlines)
        return entry.isEmpty ? nil : entry
    }

    static func url(for word: String) -> URL? {
        let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")
        guard let term = word.addingPercentEncoding(withAllowedCharacters: allowed) else { return nil }
        return URL(string: "dict://\(term)")
    }

    static func words(in text: String) -> [String] {
        var seen = Set<String>()
        return text.components(separatedBy: CharacterSet(charactersIn: ",、\n"))
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty && seen.insert($0).inserted }
    }
}

struct DictionaryWordLinks: View {
    let words: [String]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 76), alignment: .leading)], alignment: .leading, spacing: 9) {
            ForEach(words, id: \.self) { word in
                if let url = JapaneseDictionary.url(for: word) {
                    DictionaryWordLink(word: word, url: url)
                }
            }
        }
    }
}

private struct DictionaryWordLink: View {
    let word: String
    let url: URL
    @State private var overWord = false
    @State private var overPopover = false
    @State private var showingDefinition = false

    private var hovering: Bool { overWord || overPopover }

    var body: some View {
        Link(word, destination: url)
            .accessibilityHint("Click to open Dictionary.")
            .onHover { overWord = $0 }
            .task(id: hovering) {
                let inside = hovering
                guard inside != showingDefinition else { return }
                do {
                    try await Task.sleep(for: .milliseconds(inside ? 300 : 200))
                    showingDefinition = inside
                } catch { }
            }
            .popover(isPresented: $showingDefinition, arrowEdge: .bottom) {
                DictionaryDefinition(word: word, url: url)
                    .onHover { overPopover = $0 }
                    .onDisappear { overPopover = false }
            }
    }
}

private struct DictionaryDefinition: View {
    let word: String
    let url: URL
    @State private var definition: String?
    @State private var loaded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(word).font(.headline)
            if let definition {
                ScrollView {
                    Text(definition).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }.frame(maxHeight: 220)
            } else if loaded {
                Text("No definition found in the enabled macOS dictionaries.").foregroundStyle(.secondary)
            } else {
                ProgressView().controlSize(.small)
            }
            Link("Open in Dictionary", destination: url)
        }
        .padding(14)
        .frame(width: 340, alignment: .leading)
        .task(id: word) {
            let result = await Task.detached(priority: .userInitiated) {
                JapaneseDictionary.definition(for: word)
            }.value
            guard !Task.isCancelled else { return }
            definition = result
            loaded = true
        }
    }
}
