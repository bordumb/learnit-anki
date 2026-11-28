import AVFoundation
import SwiftUI
import UniformTypeIdentifiers

private struct TranscriptionDraft: Decodable {
    let text: String
}

private struct PackageResult: Decodable {
    let package: String
}

private struct PassageDestination: Decodable, Sendable {
    let name: String
}

private enum SourceKind {
    case image, audio, document, deck

    var contentTypes: [UTType] {
        switch self {
        case .image: [.image]
        case .audio: [.audio]
        case .document: [.plainText, .commaSeparatedText]
        case .deck: [UTType(filenameExtension: "apkg") ?? .data]
        }
    }
}

private enum TranscriptionError: LocalizedError {
    case process(String)
    case invalidCrop

    var errorDescription: String? {
        switch self {
        case .process(let output): return output
        case .invalidCrop: return "Select a larger region of the image."
        }
    }
}

@MainActor
struct MediaCardView: View {
    private static let languages = [("ja", "Japanese"), ("en", "English"), ("fr", "French"),
                                    ("de", "German"), ("es", "Spanish"), ("ca", "Catalan"),
                                    ("it", "Italian"), ("pt", "Portuguese")]

    private let library: StudyLibrary?
    private let decks: [StudyDeck]
    private let initialDeck: Int64?
    private let active: Bool
    private let createDeck: () -> Void
    @State private var studyDeck: Int64?

    init(library: StudyLibrary? = nil, decks: [StudyDeck] = [], initialDeck: Int64? = nil, active: Bool = true,
         createDeck: @escaping () -> Void = {}) {
        self.library = library
        self.decks = decks
        self.initialDeck = initialDeck
        self.active = active
        self.createDeck = createDeck
        _studyDeck = State(initialValue: initialDeck)
    }

    private var localDeck: StudyDeck? { decks.first { $0.id == studyDeck } ?? decks.first }

    @EnvironmentObject private var settings: AppSettings
    @State private var image: NSImage?
    @State private var imageName = ""
    @State private var documentURL: URL?
    @State private var csvColumn = "sentence"
    @State private var selection: CGRect?
    @State private var audioURL: URL?
    @State private var audioDuration: TimeInterval?
    @State private var audioPeaks: [Float] = []
    @State private var draftAudioURL: URL?
    @State private var trimAudio = false
    @State private var clipStart: TimeInterval = 0
    @State private var clipEnd: TimeInterval = 0
    @State private var draftClip: AudioClip?
    @State private var recording: MicrophoneRecording?
    private var recordingURL: URL? { recording?.url }
    @State private var recorder: AVAudioRecorder?
    @State private var player: AVAudioPlayer?
    @State private var pendingSource: SourceKind = .image
    @State private var attachImportedAudio = false
    @State private var importing = false
    @State private var busy = false
    @State private var status = ""
    @State private var draft = ""
    @AppStorage("passageTemplatePath") private var savedTemplatePath = ""
    @State private var passageDestination: PassageDestination?
    @State private var templateURL: URL?
    @State private var loadingDestination = true
    @State private var dictionaryEntries = ""
    @State private var headwords = ""
    @State private var contextNote = ""
    @State private var showCapture = false
    @State private var showPassagePreview = false
    @State private var furigana: FuriganaDraft?
    @State private var includePassagePronunciation = false
    @State private var includePassageRecording = false
    @State private var source = ""
    @State private var deckName = "Japanese"
    @State private var includeAudio = true
    @State private var includeGrammar = true
    @State private var enterTranslationManually = false
    @State private var translation = ""
    @State private var offerManualTranslation = false
    @State private var sourceLanguage = "ja"
    @State private var targetLanguage = "en"
    @State private var moreOptions = false
    @State private var exportedPackage: URL?
    @FocusState private var editorFocused: Bool

    var body: some View {
        Group {
            if library == nil && loadingDestination {
                ProgressView("Opening Learnit…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if isPassageMode {
                passageWorkspace
                    .safeAreaInset(edge: .bottom, spacing: 0) { passageFooter }
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        if documentURL != nil { captureControls }
                        editorPanel
                    }
                    .padding(28)
                    .frame(maxWidth: 780)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .frame(minWidth: 820, minHeight: 555)
        .background(Color(nsColor: .windowBackgroundColor))
        .defaultFocus($editorFocused, active)
        .toolbar {
            if active {
            ToolbarItem(placement: .navigation) {
                Menu {
                    Button("Open image…", systemImage: "photo") { choose(.image) }
                    Button("Open audio…", systemImage: "waveform") { choose(.audio) }
                    Button("Record audio", systemImage: "mic") { Task { await toggleRecording() } }
                    if library == nil {
                        Divider()
                        Button("Import text or CSV…", systemImage: "doc.text") { choose(.document) }
                    }
                } label: {
                    Label("Add source", systemImage: "paperclip")
                }
                .disabled(busy || recorder != nil)
            }
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    if library != nil {
                        ForEach(decks) { deck in
                            Button(deck.name) { studyDeck = deck.id }
                        }
                        Button("New deck…", systemImage: "plus") { createDeck() }
                    } else {
                        Button("Choose Anki package…", systemImage: "folder") { choose(.deck) }
                        Button("Use standard card format", systemImage: "rectangle.on.rectangle") {
                            passageDestination = nil
                            templateURL = nil
                            savedTemplatePath = "standard"
                        }
                    }
                } label: {
                    Label(library != nil ? localDeck?.name ?? "Choose deck" : passageDestination?.name ?? deckName,
                          systemImage: "square.stack")
                }
                .disabled(busy || recorder != nil || documentURL != nil)
            }
            }
        }
        .task(id: settings.projectPath) { if library == nil { await restoreDestination() } }
        .onChange(of: initialDeck) { if let initialDeck { studyDeck = initialDeck } }
        .onChange(of: active) {
            editorFocused = active
            if !active {
                player?.stop()
                if recorder != nil { Task { await toggleRecording() } }
            }
        }
        .onChange(of: settings.projectPath) { furigana = nil }
        .onDisappear {
            recorder?.stop()
            recorder = nil
            player?.stop()
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: pendingSource.contentTypes,
                      onCompletion: importFile)
        .sheet(isPresented: $showCapture, onDismiss: { player?.stop() }) {
            captureSheet
                .interactiveDismissDisabled(busy || recorder != nil)
        }
        .sheet(isPresented: $showPassagePreview) {
            if let library {
                passagePreview(deck: localDeck?.name ?? "Choose deck", target: localDeck.map { .study(library.database, $0.id) })
            } else if let passageDestination, let templateURL {
                passagePreview(deck: passageDestination.name, target: .anki(templateURL))
            }
        }
    }

    private enum PassageTarget: Sendable {
        case study(URL, Int64)
        case anki(URL)
    }

    private func passagePreview(deck: String, target: PassageTarget?) -> some View {
        let pronunciation = includePassagePronunciation
        let recording = includePassageRecording ? recordingForPassage : nil
        let audioLabels = [pronunciation ? "Pronunciation" : nil, recording != nil ? "Source audio" : nil].compactMap { $0 }
        return PassagePreview(deckName: deck, draft: passageDraft, audioLabels: audioLabels,
                              exportIssue: passageExportIssue, commitTitle: library == nil ? "Export to Anki" : "Save card",
                              project: settings.projectPath, furigana: $furigana) { card in
            guard let target else { return }
            commitPassage(card, target: target, pronunciation: pronunciation, recording: recording)
        }
    }

    private var isPassageMode: Bool { (library != nil || passageDestination != nil) && documentURL == nil }

    private var passageDraft: PassageDraft {
        let reference: String
        if draftAudioURL == nil, includePassageRecording, let recording = recordingForPassage {
            let label = source.isEmpty ? recording.url.lastPathComponent : source
            reference = recording.clip.map { "\(label) [\($0.timestampLabel)]" } ?? label
        } else {
            reference = sourceWithRange(draftClip)
        }
        return PassageDraft(expression: draft, definitions: dictionaryEntries, source: reference,
                            context: contextNote, translation: translation, headwords: headwords)
    }

    private var recordingForPassage: (url: URL, clip: AudioClip?)? {
        guard let audioURL, recorder == nil else { return nil }
        if draftAudioURL == audioURL { return (audioURL, draftClip) }
        guard !trimAudio || selectedClip != nil else { return nil }
        return (audioURL, selectedClip)
    }

    private var hasPassage: Bool { !PassageDraft.clean(draft).isEmpty }

    private var passageExportIssue: String? {
        if library != nil && localDeck == nil { return "Create a deck to save this card." }
        if !passageDraft.isReady {
            return "Add a dictionary link, definition, context note, or translation."
        }
        if includePassageRecording && recordingForPassage == nil { return "Choose a valid source audio range." }
        return nil
    }

    private var passageWorkspace: some View {
        HStack(alignment: .top, spacing: 0) {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Text(hasPassage ? "Passage" : "New passage").font(.title2.weight(.semibold))
                    Spacer()
                    Button("Furigana", systemImage: "textformat") { showPassagePreview = true }
                        .disabled(!hasPassage)
                        .help("Preview and edit the passage’s readings")
                }
                ZStack(alignment: .topLeading) {
                    if draft.isEmpty {
                        Text("Type or paste Japanese…")
                            .foregroundStyle(.secondary)
                            .padding(.leading, 5)
                            .allowsHitTesting(false)
                    }
                    TextEditor(text: $draft)
                        .scrollContentBackground(.hidden)
                        .focused($editorFocused)
                        .accessibilityLabel("Passage")
                }
                .font(.system(.title2, design: .serif))
                .lineSpacing(6)
                .frame(minHeight: 180)

                if let audioURL {
                    HStack {
                        Button("Replay audio", systemImage: "play.circle") {
                            preview(audioURL, clip: draftAudioURL == audioURL ? draftClip : selectedClip)
                        }
                        .labelStyle(.iconOnly)
                        .buttonStyle(.borderless)
                        if let draftClip, draftAudioURL == audioURL {
                            Text(draftClip.timestampLabel).monospacedDigit()
                        }
                        Button(audioURL == recordingURL ? "Recorded conversation" : audioURL.lastPathComponent) {
                            showCapture = true
                        }
                        .buttonStyle(.link)
                        .lineLimit(1)
                    }
                    .foregroundStyle(.secondary)
                } else if image != nil {
                    Button(imageName, systemImage: "photo") { showCapture = true }
                        .buttonStyle(.link)
                }
            }
            .padding(28)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)

            if hasPassage || !passageDraft.meaning.isEmpty {
                Divider()
                ScrollView {
                    passageMeaning
                        .padding(24)
                }
                .background(Color(nsColor: .controlBackgroundColor))
                .frame(idealWidth: 380, maxWidth: 460, maxHeight: .infinity)
            }
        }
        .disabled(busy || recorder != nil)
    }

    private var passageMeaning: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Meaning").font(.title2.weight(.semibold))
            HStack {
                Text("Dictionary links").font(.headline)
                Spacer()
                Button("Look up words", systemImage: "book.closed") { lookUpPassage() }
                    .disabled(!hasPassage)
            }
            TextField("Separate words with commas (e.g. 父、寡黙)", text: $headwords)
                .accessibilityLabel("Dictionary links")
            let words = JapaneseDictionary.words(in: headwords)
            if !words.isEmpty {
                DictionaryWordLinks(words: words)
            }
            Text("Definition notes (optional)").font(.subheadline)
            TextEditor(text: $dictionaryEntries)
                .font(.body)
                .padding(4)
                .frame(minHeight: 65)
                .accessibilityLabel("Japanese dictionary entries")
                .overlay { RoundedRectangle(cornerRadius: 6).strokeBorder(.separator).allowsHitTesting(false) }
            TextField("Source or page", text: $source, axis: .vertical).lineLimit(1...3)
            TextField("Context note", text: $contextNote, axis: .vertical).lineLimit(2...5)
            HStack {
                Text("English translation").font(.headline)
                Spacer()
                Button("Translate") { translatePassage() }
                    .disabled(!hasPassage)
            }
            TextEditor(text: $translation)
                .font(.body)
                .padding(4)
                .frame(minHeight: 90)
                .accessibilityLabel("English translation")
                .overlay { RoundedRectangle(cornerRadius: 6).strokeBorder(.separator).allowsHitTesting(false) }
        }
        .textFieldStyle(.roundedBorder)
    }

    private var passageFooter: some View {
        VStack(alignment: .leading, spacing: 0) {
            Divider()
            if hasPassage {
                HStack(spacing: 20) {
                    Toggle("Pronunciation audio", isOn: $includePassagePronunciation)
                    if audioURL != nil {
                        Toggle("Include source audio", isOn: $includePassageRecording)
                            .disabled(recordingForPassage == nil)
                    } else {
                        Button("Attach audio…", systemImage: "paperclip") { choose(.audio, attachAudio: true) }
                            .buttonStyle(.link)
                    }
                }
                .toggleStyle(.checkbox)
                .disabled(busy || recorder != nil)
                .padding(.horizontal, 24)
                .padding(.top, 12)
            }
            HStack(spacing: 10) {
                if busy { ProgressView().controlSize(.small) }
                if !status.isEmpty {
                    Text(status).font(.callout).textSelection(.enabled)
                }
                Spacer()
                if library != nil && localDeck == nil {
                    Button("New deck…", action: createDeck).disabled(busy || recorder != nil)
                }
                if let exportedPackage {
                    Button("Show in Finder") { NSWorkspace.shared.activateFileViewerSelecting([exportedPackage]) }
                    Button("Open in Anki") { openPackage(exportedPackage) }
                    Button("New passage") { clearPassage() }
                        .disabled(busy)
                }
                Button("Preview card") { showPassagePreview = true }
                    .buttonStyle(.borderedProminent)
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(!active || busy || recorder != nil || passageExportIssue != nil)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 13)
        }
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var captureSheet: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(image != nil ? "Choose a passage" : "Choose an excerpt")
                .font(.title2.weight(.semibold))
            captureControls
            if busy { ProgressView().controlSize(.small) }
            if !status.isEmpty {
                Text(status).font(.callout).textSelection(.enabled)
            }
            HStack {
                Spacer()
                Button("Done") { showCapture = false }
                    .disabled(busy || recorder != nil)
                    .keyboardShortcut(.cancelAction)
            }
        }
        .padding(24)
        .frame(width: 640)
    }

    private var captureControls: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let image {
                attachmentHeader(imageName)
                ImagePhrasePicker(image: image, selection: $selection)
                    .frame(height: 285)
                    .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 8))
                    .allowsHitTesting(!busy)
                Text("Drag around the passage, or recognize the whole image.")
                    .font(.caption).foregroundStyle(.secondary)
                HStack {
                    Button("Recognize on Mac", systemImage: "text.viewfinder") { readMedia(onMac: true) }
                        .buttonStyle(.borderedProminent)
                        .disabled(!isPassageMode && sourceLanguage != "ja")
                    Button("Use Google instead") { readMedia() }
                }
                .disabled(busy)
            } else if let audioURL {
                attachmentHeader(audioURL == recordingURL ? "Recorded conversation" : audioURL.lastPathComponent)
                if recorder != nil {
                    Button("Stop recording", systemImage: "stop.circle") { Task { await toggleRecording() } }
                } else {
                    audioControls(audioURL)
                }
            } else if let documentURL {
                attachmentHeader(documentURL.lastPathComponent)
                if isCSV {
                    TextField("CSV column", text: $csvColumn)
                        .textFieldStyle(.roundedBorder)
                        .disabled(busy)
                }
            }
        }
    }

    private func attachmentHeader(_ filename: String) -> some View {
        HStack {
            Text(filename)
                .font(.callout.weight(.medium))
                .lineLimit(1)
                .truncationMode(.middle)
                .help(filename)
            Spacer()
            Button("Remove attachment", systemImage: "xmark.circle", action: { removeAttachment(); showCapture = false })
                .labelStyle(.iconOnly)
                .buttonStyle(.borderless)
                .help("Remove attachment")
                .disabled(busy || recorder != nil)
        }
    }

    private var editorPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let documentURL {
                Text("Imported text").font(.title3.bold())
                Text("Create cards from \(documentURL.lastPathComponent).")
                    .foregroundStyle(.secondary)
            } else {
                Text(sourceLanguage == "ja" ? "Japanese text" : "Card text")
                    .font(.title3.bold())
                    .accessibilityAddTraits(.isHeader)
                Text("Type, paste, or edit the recognized text.")
                    .foregroundStyle(.secondary)
                TextEditor(text: $draft)
                    .font(.title3)
                    .scrollContentBackground(.hidden)
                    .padding(9)
                    .frame(height: 168)
                    .background(Color(nsColor: .textBackgroundColor), in: RoundedRectangle(cornerRadius: 8))
                    .overlay {
                        RoundedRectangle(cornerRadius: 8)
                            .strokeBorder(editorFocused ? Color.accentColor : Color(nsColor: .separatorColor))
                            .allowsHitTesting(false)
                    }
                    .accessibilityLabel("Card text")
                    .focused($editorFocused)
                    .disabled(busy)
                if image != nil || audioURL != nil {
                    Button("Show source") { showCapture = true }
                }
                if !source.isEmpty {
                    Text("From \(sourceWithRange(draftClip))")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
                if enterTranslationManually {
                    TextField("Translation", text: $translation, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(2...4)
                        .disabled(busy)
                    Text("Uses your translation and optional pronunciation audio.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Divider().padding(.vertical, 6)
            cardOptions.disabled(busy)
            exportControls
        }
    }

    private var cardOptions: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Card options").font(.title3.bold())
                .accessibilityAddTraits(.isHeader)
            LabeledContent("Deck") {
                TextField("Deck name", text: $deckName)
                    .labelsHidden()
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 270)
            }
            Toggle("Pronunciation audio", isOn: $includeAudio)
            DisclosureGroup("More options", isExpanded: $moreOptions) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        languagePicker("Source", selection: $sourceLanguage)
                        languagePicker("Translation", selection: $targetLanguage)
                    }
                    Toggle("Grammar notes", isOn: $includeGrammar)
                        .disabled(documentURL == nil && enterTranslationManually)
                    if documentURL == nil {
                        Toggle("Enter translation manually", isOn: $enterTranslationManually)
                        TextField("Source URL or label", text: $source)
                            .textFieldStyle(.roundedBorder)
                    }
                    if sourceLanguage == targetLanguage {
                        Text("Choose two different languages.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.top, 8)
            }
        }
        .toggleStyle(.checkbox)
    }

    private func languagePicker(_ title: String, selection: Binding<String>) -> some View {
        Picker(title, selection: selection) {
            ForEach(Self.languages, id: \.0) { code, name in
                Text(name).tag(code)
            }
        }
    }

    private var exportControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                if busy { ProgressView().controlSize(.small) }
                if !status.isEmpty {
                    Text(status).font(.caption).textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
                Button(documentURL == nil ? "Create card" : "Create deck", action: createCard)
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(!canExport)
            }
            if offerManualTranslation && !enterTranslationManually && documentURL == nil {
                Button("Use my own translation") { enterTranslationManually = true }
            }
            if let exportedPackage {
                HStack {
                    Text(exportedPackage.lastPathComponent)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button("Show in Finder") {
                        NSWorkspace.shared.activateFileViewerSelecting([exportedPackage])
                    }
                    Button("Open in Anki") {
                        if !NSWorkspace.shared.open(exportedPackage) {
                            status = "Could not open the package. Use Show in Finder to locate it."
                        }
                    }
                }
                .font(.callout)
            }
        }
        .padding(.top, 6)
    }

    private var isCSV: Bool { documentURL?.pathExtension.lowercased() == "csv" }

    private var canExport: Bool {
        !busy && recorder == nil && sourceLanguage != targetLanguage
            && !deckName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && (documentURL != nil || !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            && (documentURL != nil || !enterTranslationManually
                || !translation.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            && (!isCSV || !csvColumn.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
    }

    private func importFile(_ result: Result<URL, Error>) {
        do {
            let url = try result.get()
            if pendingSource == .deck {
                Task { await loadDestination(url) }
                return
            }
            let pickedImage: NSImage?
            if pendingSource == .image {
                let data = try withAccess(url) { try Data(contentsOf: url) }
                guard let decoded = NSImage(data: data) else {
                    throw TranscriptionError.process("Could not read this image.")
                }
                pickedImage = decoded
            } else {
                pickedImage = nil
            }

            removeAttachment()
            switch pendingSource {
            case .image:
                image = pickedImage
                imageName = url.lastPathComponent
                showCapture = true
            case .audio:
                audioURL = url
                includePassageRecording = attachImportedAudio
                showCapture = true
                Task { await loadAudioDuration(url) }
            case .document:
                documentURL = url
                csvColumn = "sentence"
            case .deck:
                return
            }
        } catch let error as CocoaError where error.code == .userCancelled {
            return
        } catch {
            status = error.localizedDescription
        }
    }

    private func removeAttachment() {
        player?.stop()
        audioURL = nil
        includePassageRecording = false
        recording = nil
        image = nil
        imageName = ""
        selection = nil
        documentURL = nil
        resetAudioRange()
        status = ""
    }

    private var selectedClip: AudioClip? {
        guard trimAudio, let audioDuration else { return nil }
        return AudioClip(start: clipStart, end: clipEnd, duration: audioDuration)
    }

    private func audioControls(_ url: URL) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Button("Play / stop") { preview(url, clip: selectedClip) }
                    .disabled(trimAudio && selectedClip == nil)
                if let audioDuration {
                    Text(AudioClip.timestamp(audioDuration))
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                }
            }
            if let audioDuration {
                if !audioPeaks.isEmpty {
                    AudioWaveformView(peaks: audioPeaks, duration: audioDuration, trimming: trimAudio,
                                      start: $clipStart, end: $clipEnd)
                        .onChange(of: clipStart) { player?.stop() }
                        .onChange(of: clipEnd) { player?.stop() }
                }
                Toggle("Select a time range", isOn: $trimAudio)
                    .onChange(of: trimAudio) { player?.stop() }
                if trimAudio {
                    clipBoundary("Start", value: $clipStart, duration: audioDuration)
                    clipBoundary("End", value: $clipEnd, duration: audioDuration)
                    if selectedClip == nil {
                        Text("Choose a start and end within the recording, with the end after the start.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            Button(trimAudio ? "Transcribe excerpt" : "Transcribe audio") { readMedia() }
                .buttonStyle(.borderedProminent)
                .disabled(trimAudio && selectedClip == nil)
        }
        .disabled(busy || recorder != nil)
    }

    private func clipBoundary(_ label: String, value: Binding<TimeInterval>, duration: TimeInterval) -> some View {
        HStack {
            Slider(value: value, in: 0...duration) { Text(label) }
                .accessibilityValue(AudioClip.timestamp(value.wrappedValue))
            TextField("\(label) in seconds", value: value, format: .number.precision(.fractionLength(2)))
                .multilineTextAlignment(.trailing)
                .textFieldStyle(.roundedBorder)
                .frame(width: 82)
            Text("s").foregroundStyle(.secondary)
        }
        .onChange(of: value.wrappedValue) { player?.stop() }
    }

    private func resetAudioRange() {
        audioDuration = nil
        audioPeaks = []
        trimAudio = false
        clipStart = 0
        clipEnd = 0
    }

    private func loadAudioDuration(_ url: URL) async {
        guard let duration = await AudioClip.duration(of: url),
              duration.isFinite, duration > 0, audioURL == url, recorder == nil else { return }
        audioDuration = duration
        clipEnd = duration
        trimAudio = duration > 30
        let peaks = await AudioWaveform.peaks(of: url)
        if audioURL == url, !Task.isCancelled { audioPeaks = peaks }
    }

    private func choose(_ kind: SourceKind, attachAudio: Bool = false) {
        guard recorder == nil else { return }
        pendingSource = kind
        attachImportedAudio = attachAudio
        importing = true
    }

    private func toggleRecording() async {
        if let recorder {
            recorder.stop()
            self.recorder = nil
            status = "Recording ready to transcribe."
            if let recordingURL { await loadAudioDuration(recordingURL) }
            return
        }
        busy = true
        let authorized = await AVCaptureDevice.requestAccess(for: .audio)
        busy = false
        guard authorized else {
            status = "Allow microphone access in System Settings to record audio."
            return
        }
        do {
            let newRecording = MicrophoneRecording()
            let newRecorder = try AVAudioRecorder(url: newRecording.url, settings: [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 44100,
                AVNumberOfChannelsKey: 1,
            ])
            guard newRecorder.record() else {
                throw TranscriptionError.process("Could not start recording.")
            }
            removeAttachment()
            recording = newRecording
            audioURL = newRecording.url
            recorder = newRecorder
            status = "Recording…"
            showCapture = true
        } catch {
            status = error.localizedDescription
        }
    }

    private func preview(_ url: URL, clip: AudioClip?) {
        if let player, player.isPlaying {
            player.stop()
            return
        }
        busy = true
        Task {
            defer { busy = false }
            do {
                let temporary = try await clip?.export(from: url)
                defer { if let temporary { try? FileManager.default.removeItem(at: temporary) } }
                let input = temporary ?? url
                let data = try withAccess(input) { try Data(contentsOf: input) }
                let newPlayer = try AVAudioPlayer(data: data)
                if newPlayer.play() { player = newPlayer }
                else { status = "Could not play this audio." }
            } catch {
                status = error.localizedDescription
            }
        }
    }

    private func readMedia(onMac: Bool = false) {
        let clip = selectedClip
        let projectPath = settings.projectPath
        let language = isPassageMode ? "ja" : sourceLanguage
        let mediaName = image != nil ? imageName
            : (audioURL == recordingURL ? "Microphone recording" : audioURL?.lastPathComponent ?? "")
        player?.stop()
        busy = true
        status = image == nil ? "Transcribing…" : "Recognizing text…"
        Task {
            var temporary: URL?
            defer {
                busy = false
                if let temporary { try? FileManager.default.removeItem(at: temporary) }
            }
            do {
                let text: String
                if let image {
                    let crop = try selectedImage(from: image)
                    if onMac {
                        text = try await ImageOCR.readOnMac(crop)
                    } else {
                        let input = try ImageOCR.writeUploadImage(crop)
                        temporary = input
                        text = try await transcribe(projectPath, "ocr", input, language)
                    }
                } else if let audioURL {
                    temporary = try await clip?.export(from: audioURL)
                    text = try await transcribe(projectPath, "transcribe", temporary ?? audioURL, language)
                } else {
                    return
                }

                guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                    status = "No text was detected. Try another selection or type the phrase."
                    return
                }
                draft = text
                draftAudioURL = audioURL
                dictionaryEntries = ""
                headwords = ""
                translation = ""
                offerManualTranslation = false
                source = mediaName
                draftClip = clip
                status = ""
                busy = false
                showCapture = false
                editorFocused = true
            } catch {
                status = error.localizedDescription
            }
        }
    }

    private func transcribe(_ project: String, _ command: String, _ input: URL, _ language: String) async throws -> String {
        try await Task.detached(priority: .userInitiated) {
            let output = try AppCLI.run(project, command: command,
                                       arguments: ["--language", language, "--", input.path], accessing: input)
            return try AppCLI.result(TranscriptionDraft.self, from: output).text
        }.value
    }

    private func selectedImage(from image: NSImage) throws -> CGImage {
        guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            throw TranscriptionError.process("Could not decode the image.")
        }
        if let selection {
            let width = CGFloat(cgImage.width)
            let height = CGFloat(cgImage.height)
            let bounds = CGRect(x: 0, y: 0, width: width, height: height)
            let pixels = CGRect(
                x: selection.minX * width, y: selection.minY * height,
                width: selection.width * width, height: selection.height * height
            ).integral.intersection(bounds)
            guard pixels.width > 2, pixels.height > 2, let cropped = cgImage.cropping(to: pixels) else {
                throw TranscriptionError.invalidCrop
            }
            return cropped
        }
        return cgImage
    }

    private func createCard() {
        let projectPath = settings.projectPath
        let batch = documentURL
        var args = ["--json-result", "--deck-name", deckName.trimmingCharacters(in: .whitespacesAndNewlines),
                    "-s", sourceLanguage, "-t", targetLanguage]
        if includeAudio { args.append("--audio") }
        if !includeGrammar { args.append("--no-grammar") }
        if let batch {
            if isCSV { args += ["--column", csvColumn.trimmingCharacters(in: .whitespacesAndNewlines)] }
            args += ["--", batch.path]
        } else {
            let label = sourceWithRange(draftClip)
            if !label.isEmpty { args += ["--source", label] }
            if enterTranslationManually { args += ["--translation=\(translation)"] }
            args += ["--", draft]
        }

        busy = true
        status = batch == nil ? "Creating card…" : "Creating deck…"
        offerManualTranslation = false
        exportedPackage = nil
        let arguments = args
        Task {
            defer { busy = false }
            do {
                let output = try await Task.detached(priority: .userInitiated) {
                    try AppCLI.run(projectPath, command: batch == nil ? "add" : "batch",
                                   arguments: arguments, accessing: batch)
                }.value
                let result = try AppCLI.result(PackageResult.self, from: output)
                exportedPackage = URL(fileURLWithPath: result.package)
                if output.contains("Saving the card without pronunciation audio.") {
                    status = "Package saved. Some pronunciation audio could not be generated."
                } else if output.contains("Skipping card for sentence") {
                    status = "Package saved. Some cards could not be generated."
                } else {
                    status = "Package ready to import."
                }
            } catch {
                status = error.localizedDescription
                offerManualTranslation = (error as? CLIError)?.isTranslationFailure == true
            }
        }
    }

    private func restoreDestination() async {
        loadingDestination = true
        defer { loadingDestination = false }
        guard savedTemplatePath != "standard" else { return }
        let defaultURL = URL(fileURLWithPath: settings.projectPath, isDirectory: true)
            .appendingPathComponent("output/nihongo-deck-repaired.apkg")
        if !savedTemplatePath.isEmpty {
            await loadDestination(URL(fileURLWithPath: savedTemplatePath))
        } else if FileManager.default.fileExists(atPath: defaultURL.path) {
            await loadDestination(defaultURL)
        }
    }

    private func loadDestination(_ url: URL) async {
        let project = settings.projectPath
        busy = true
        defer { busy = false }
        do {
            let destination = try await Task.detached {
                let output = try AppCLI.run(project, command: "passage-deck",
                                            arguments: ["--", url.path], accessing: url)
                return try AppCLI.result(PassageDestination.self, from: output)
            }.value
            guard project == settings.projectPath, !Task.isCancelled else { return }
            passageDestination = destination
            templateURL = url
            savedTemplatePath = url.path
            status = ""
        } catch {
            status = error.localizedDescription
        }
    }

    private func lookUpPassage() {
        let passage = draft
        let project = settings.projectPath
        busy = true
        status = "Looking up words…"
        Task {
            defer { busy = false }
            do {
                let results = try await AppCLI.analyzePassage([String].self, project: project,
                                                              command: "dictionary-headwords", text: passage)
                guard draft == passage else { return }
                let current = JapaneseDictionary.words(in: headwords)
                let additions = results.filter { !current.contains($0) }
                if !additions.isEmpty { headwords = (current + additions).joined(separator: "、") }
                status = results.isEmpty ? "No headwords found. You can enter dictionary links manually."
                    : additions.isEmpty ? "These dictionary links are already in the draft." : ""
            } catch {
                status = error.localizedDescription
            }
        }
    }

    private func translatePassage() {
        let project = settings.projectPath
        let passage = draft
        busy = true
        status = "Translating passage…"
        Task {
            defer { busy = false }
            do {
                let result = try await Task.detached(priority: .userInitiated) {
                    let output = try AppCLI.run(project, command: "translate-passage", arguments: ["--", passage])
                    return try AppCLI.result(TranscriptionDraft.self, from: output).text
                }.value
                translation = result
                status = ""
            } catch {
                status = "\(error.localizedDescription) You can enter the translation manually."
            }
        }
    }

    private func commitPassage(_ approved: PassageDraft, target: PassageTarget, pronunciation: Bool,
                               recording: (url: URL, clip: AudioClip?)?) {
        let project = settings.projectPath
        busy = true
        status = library == nil ? "Exporting passage…" : "Saving card…"
        exportedPackage = nil
        Task {
            defer { busy = false }
            do {
                let package: String? = try await Task.detached(priority: .userInitiated) {
                    let directory = FileManager.default.temporaryDirectory
                        .appendingPathComponent(UUID().uuidString, isDirectory: true)
                    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
                    defer { try? FileManager.default.removeItem(at: directory) }
                    let json = directory.appendingPathComponent("passage.json")
                    try JSONEncoder().encode(approved).write(to: json)
                    var arguments: [String] = []
                    if pronunciation {
                        let voice = try AudioClip.writeJapanesePronunciation(PassageDraft.clean(approved.expression),
                                                                            in: directory)
                        arguments += ["--pronunciation", voice.path]
                    }
                    var excerpt: URL?
                    defer { if let excerpt { try? FileManager.default.removeItem(at: excerpt) } }
                    if let recording {
                        excerpt = try await recording.clip?.export(from: recording.url)
                        arguments += ["--recording", (excerpt ?? recording.url).path]
                    }
                    let write = { () throws -> String? in
                        switch target {
                        case let .anki(template):
                            let output = try AppCLI.run(project, command: "export-passage",
                                                        arguments: arguments + ["--", template.path, json.path], accessing: template)
                            return try AppCLI.result(PackageResult.self, from: output).package
                        case let .study(database, deck):
                            let output = try AppCLI.run(project, command: "study",
                                                        arguments: ["--database", database.path, "save"] + arguments + ["--", String(deck), json.path])
                            _ = try AppCLI.result(StudyCardID.self, from: output)
                            return nil
                        }
                    }
                    if let recording { return try withAccess(recording.url, action: write) }
                    return try write()
                }.value
                if let package {
                    exportedPackage = URL(fileURLWithPath: package)
                    status = "Package ready to import."
                } else {
                    clearPassage()
                    status = "Card saved."
                    await library?.collectionChanged()
                }
            } catch {
                status = error.localizedDescription
            }
        }
    }

    private func openPackage(_ package: URL) {
        if !NSWorkspace.shared.open(package) {
            status = "Could not open the package. Use Show in Finder to locate it."
        }
    }

    private func clearPassage() {
        removeAttachment()
        draft = ""
        furigana = nil
        draftClip = nil
        draftAudioURL = nil
        source = ""
        dictionaryEntries = ""
        headwords = ""
        contextNote = ""
        translation = ""
        exportedPackage = nil
        editorFocused = true
    }

    private func sourceWithRange(_ clip: AudioClip?) -> String {
        guard let clip else { return source }
        let label = source.isEmpty ? "Audio" : source
        return "\(label) [\(clip.timestampLabel)]"
    }
}

private final class MicrophoneRecording {
    let url = FileManager.default.temporaryDirectory
        .appendingPathComponent(UUID().uuidString).appendingPathExtension("m4a")

    deinit { try? FileManager.default.removeItem(at: url) }
}

private func withAccess<T>(_ url: URL, action: () throws -> T) rethrows -> T {
    let accessed = url.startAccessingSecurityScopedResource()
    defer { if accessed { url.stopAccessingSecurityScopedResource() } }
    return try action()
}

private struct ImagePhrasePicker: View {
    let image: NSImage
    @Binding var selection: CGRect?

    var body: some View {
        GeometryReader { geometry in
            let scale = min(geometry.size.width / max(image.size.width, 1),
                            geometry.size.height / max(image.size.height, 1))
            let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
            Image(nsImage: image)
                .resizable()
                .frame(width: size.width, height: size.height)
                .overlay(alignment: .topLeading) {
                    if let selection {
                        Rectangle()
                            .strokeBorder(Color.accentColor, lineWidth: 2)
                            .background(Color.accentColor.opacity(0.16))
                            .frame(width: selection.width * size.width, height: selection.height * size.height)
                            .offset(x: selection.minX * size.width, y: selection.minY * size.height)
                            .allowsHitTesting(false)
                    }
                }
                .gesture(DragGesture(minimumDistance: 2).onChanged { drag in
                    let first = unitPoint(drag.startLocation, size)
                    let last = unitPoint(drag.location, size)
                    selection = CGRect(x: min(first.x, last.x), y: min(first.y, last.y),
                                       width: abs(first.x - last.x), height: abs(first.y - last.y))
                })
                .onTapGesture { selection = nil }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .accessibilityLabel("Source image. Drag to crop or click to reset.")
    }

    private func unitPoint(_ point: CGPoint, _ size: CGSize) -> CGPoint {
        CGPoint(x: min(1, max(0, point.x / max(1, size.width))),
                y: min(1, max(0, point.y / max(1, size.height))))
    }
}
