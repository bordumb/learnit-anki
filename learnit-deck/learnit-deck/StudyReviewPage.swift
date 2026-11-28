import AVFoundation
import SwiftUI
import WebKit

struct StudyReviewPage: View {
    @ObservedObject var library: StudyLibrary
    let deck: Int64?
    let finish: () -> Void
    @State private var current: StudyCard?
    @State private var nextDue: Double?
    @State private var revealed = false
    @State private var working = true
    @State private var started = Date()
    @State private var completed = 0
    @State private var issue: String?
    @State private var player: AVAudioPlayer?

    var body: some View {
        StudyPageLayout("Review", subtitle: deck.flatMap { id in
            library.summary.decks.first { $0.id == id }?.name
        } ?? "All decks") {
            if let current {
                HStack {
                    Text("\(completed.formatted()) reviewed in this session").foregroundStyle(.secondary)
                    Spacer()
                    Button("End session", action: finish).disabled(working)
                }
                StudyPanel {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Passage").font(.subheadline).foregroundStyle(.secondary)
                        StudyHTML(current.frontHtml, size: 26).frame(height: 112)
                        if revealed {
                            Divider()
                            if !current.readingHtml.isEmpty {
                                StudyHTML(current.readingHtml, size: 21).frame(height: 85)
                            }
                            if !current.dictionaryWords.isEmpty {
                                DictionaryWordLinks(words: current.dictionaryWords)
                            }
                            let meaningHTML = current.meaningBodyHtml ?? current.backHtml
                            if !meaningHTML.isEmpty {
                                StudyHTML(meaningHTML, size: 16, serif: false).frame(height: 235)
                            }
                            if !current.audio.isEmpty {
                                HStack {
                                    ForEach(current.audio) { track in
                                        Button(track.label, systemImage: "speaker.wave.2") { play(track) }
                                    }
                                }
                            }
                        }
                    }
                }
                if revealed {
                    HStack(spacing: 9) {
                        ForEach(Array(zip(["Again", "Hard", "Good", "Easy"], current.grades).enumerated()), id: \.offset) { index, option in
                            if index == 2 {
                                rateButton(index, option: option, card: current).buttonStyle(.borderedProminent)
                            } else {
                                rateButton(index, option: option, card: current).buttonStyle(.bordered)
                            }
                        }
                    }.disabled(working)
                } else {
                    Button("Show answer") {
                        revealed = true
                        if library.summary.preferences.autoAudio != 0, let track = current.audio.first { play(track) }
                    }
                    .buttonStyle(.borderedProminent)
                    .keyboardShortcut(.space, modifiers: [])
                    .disabled(working)
                }
            } else if working {
                ProgressView("Loading the review queue…")
            } else if issue == nil {
                StudyPanel(tinted: true) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(completed == 0 ? "You’re caught up for now" : "Session complete")
                            .font(.title2.weight(.semibold))
                        if let nextDue {
                            let date = Date(timeIntervalSince1970: nextDue)
                            Text("Next review \(date.formatted(date: .abbreviated, time: .shortened)).")
                                .foregroundStyle(.secondary)
                        }
                        HStack {
                            Button("Back to Today", action: finish).buttonStyle(.borderedProminent)
                            Button("Refresh queue") { Task { await reload() } }
                        }
                    }
                }
            }
            if let issue {
                StudyPanel {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(issue)
                        Button("Reload queue") { Task { await reload() } }
                    }
                }
            }
        }
        .task { await reload() }
        .onDisappear { player?.stop() }
    }

    private func rateButton(_ index: Int, option: (String, String), card: StudyCard) -> some View {
        Button {
            working = true
            Task {
                do {
                    let milliseconds = Int(max(0, Date().timeIntervalSince(started)) * 1000)
                    let _ = try await library.request(StudyGrade.self, [
                        "grade", String(card.id), String(card.revision), String(index + 1), String(milliseconds),
                    ])
                    completed += 1
                    await reload()
                    await library.load()
                } catch {
                    issue = error.localizedDescription
                    working = false
                }
            }
        } label: {
            VStack(spacing: 3) {
                Text(option.0).font(.body.weight(.medium))
                Text(option.1).font(.caption)
            }.frame(maxWidth: .infinity).padding(.vertical, 4)
        }
        .keyboardShortcut(KeyEquivalent(Character(String(index + 1))), modifiers: [])
    }

    private func reload() async {
        working = true
        issue = nil
        defer { working = false }
        player?.stop()
        do {
            let options = deck.map { ["--deck", String($0)] } ?? []
            let result = try await library.request(StudyNextCard.self, ["next-card"] + options)
            guard !Task.isCancelled else { return }
            current = result.card
            nextDue = result.nextDue
            revealed = false
            started = Date()
        } catch { issue = error.localizedDescription }
    }

    private func play(_ track: StudyTrack) {
        do {
            player?.stop()
            player = try AVAudioPlayer(contentsOf: URL(fileURLWithPath: track.path))
            player?.play()
        } catch { issue = "Could not play \(track.label)." }
    }
}

struct StudyHTML: NSViewRepresentable {
    let html: String
    let size: Int
    var serif = true

    init(_ html: String, size: Int, serif: Bool = true) {
        self.html = html
        self.size = size
        self.serif = serif
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = false
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        view.underPageBackgroundColor = .clear
        return view
    }

    func updateNSView(_ view: WKWebView, context: Context) {
        let document = """
        <!doctype html><html lang="ja"><head><meta charset="utf-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'">
        <style>
        :root { color-scheme: light dark; }
        body { margin: 2px; color: CanvasText; background: transparent;
               font: \(size)px/1.65 \(serif ? "ui-serif, serif" : "-apple-system, sans-serif");
               overflow-wrap: anywhere; }
        img { max-width: 100%; height: auto; } ruby { ruby-position: over; } rt { font-size: 0.57em; }
        </style></head><body>\(html)</body></html>
        """
        if context.coordinator.document != document {
            context.coordinator.document = document
            view.loadHTMLString(document, baseURL: nil)
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var document = ""

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if action.navigationType == .linkActivated, let url = action.request.url,
               ["dict", "https", "http"].contains(url.scheme?.lowercased() ?? "") {
                NSWorkspace.shared.open(url)
                decisionHandler(.cancel)
            } else {
                decisionHandler(action.request.url?.absoluteString == "about:blank" ? .allow : .cancel)
            }
        }
    }
}
