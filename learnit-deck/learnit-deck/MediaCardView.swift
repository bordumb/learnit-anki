import AVFoundation
import SwiftUI
import UniformTypeIdentifiers

private struct TranscriptionDraft: Decodable {
    let text: String
}

private enum TranscriptionError: LocalizedError {
    case process(String)
    case noDraft
    case invalidCrop

    var errorDescription: String? {
        switch self {
        case .process(let output): return output
        case .noDraft: return "The transcription command did not return a draft."
        case .invalidCrop: return "Select a larger region of the image."
        }
    }
}

@MainActor
struct MediaCardView: View {
    @EnvironmentObject private var settings: AppSettings
    @State private var image: NSImage?
    @State private var selection: CGRect?
    @State private var audioURL: URL?
    @State private var audioDuration: TimeInterval?
    @State private var trimAudio = false
    @State private var clipStart: TimeInterval = 0
    @State private var clipEnd: TimeInterval = 0
    @State private var draftClip: AudioClip?
    @State private var recordingURL: URL?
    @State private var recorder: AVAudioRecorder?
    @State private var player: AVAudioPlayer?
    @State private var choosingImage = false
    @State private var importing = false
    @State private var busy = false
    @State private var status = ""
    @State private var draft = ""
    @State private var source = ""
    @State private var deckName = "Japanese"
    @State private var includeAudio = true

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Button("Open Image") { choose(image: true) }
                    Button("Open Audio") { choose(image: false) }
                    Button(recorder == nil ? "Record Audio" : "Stop Recording") {
                        Task { await toggleRecording() }
                    }
                }
                .disabled(busy)
                if let image {
                    ImagePhrasePicker(image: image, selection: $selection)
                        .frame(height: 185)
                        .allowsHitTesting(!busy)
                    Text("Drag to select the phrase, or use the whole image.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Button("Read Image") { readMedia() }
                        .disabled(busy || recorder != nil)
                } else if let audioURL {
                    audioControls(audioURL)
                }
                Text("Japanese text")
                    .font(.headline)
                TextEditor(text: $draft)
                    .font(.body)
                    .frame(minHeight: 82)
                    .border(Color.secondary.opacity(0.35))
                    .accessibilityLabel("Japanese text")
                    .disabled(busy)
                TextField("Source URL or label", text: $source)
                TextField("Anki deck", text: $deckName)
                Toggle("Generate pronunciation audio", isOn: $includeAudio)
                Button("Create Card") { createCard() }
                    .disabled(busy || recorder != nil || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || deckName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                if busy { ProgressView() }
                if !status.isEmpty {
                    Text(status).font(.caption).textSelection(.enabled)
                }
            }
            .padding()
        }
        .onDisappear {
            recorder?.stop()
            recorder = nil
            player?.stop()
        }
        .fileImporter(
            isPresented: $importing,
            allowedContentTypes: choosingImage ? [.image] : [.audio]
        ) { result in
            do {
                let url = try result.get()
                player?.stop()
                if choosingImage {
                    let data = try withAccess(url) { try Data(contentsOf: url) }
                    guard let newImage = NSImage(data: data) else {
                        throw TranscriptionError.process("Could not read this image.")
                    }
                    image = newImage
                    selection = nil
                    audioURL = nil
                } else {
                    image = nil
                    audioURL = url
                    Task { await loadAudioDuration(url) }
                }
                resetAudioRange()
                draft = ""
                status = ""
                source = url.lastPathComponent
            } catch {
                status = error.localizedDescription
            }
        }
    }

    private var selectedClip: AudioClip? {
        guard trimAudio, let audioDuration else { return nil }
        return AudioClip(start: clipStart, end: clipEnd, duration: audioDuration)
    }

    private func audioControls(_ url: URL) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(url == recordingURL ? "Recording" : url.lastPathComponent)
                    .lineLimit(1)
                if let audioDuration {
                    Text(AudioClip.timestamp(audioDuration)).monospacedDigit().foregroundStyle(.secondary)
                }
                Button("Play or Stop") { preview(url) }
                    .disabled(trimAudio && selectedClip == nil)
                Button(trimAudio ? "Transcribe Selection" : "Transcribe Audio") { readMedia() }
                    .disabled(trimAudio && selectedClip == nil)
            }
            if let audioDuration {
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
        trimAudio = false
        clipStart = 0
        clipEnd = 0
        draftClip = nil
    }

    private func loadAudioDuration(_ url: URL) async {
        guard let duration = await AudioClip.duration(of: url),
              duration.isFinite, duration > 0, audioURL == url, recorder == nil else { return }
        audioDuration = duration
        clipEnd = duration
    }

    private func choose(image: Bool) {
        guard recorder == nil else { return }
        choosingImage = image
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
        guard await AVCaptureDevice.requestAccess(for: .audio) else {
            status = "Allow microphone access in System Settings to record audio."
            return
        }
        do {
            player?.stop()
            let url = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString).appendingPathExtension("m4a")
            let newRecorder = try AVAudioRecorder(url: url, settings: [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 44100,
                AVNumberOfChannelsKey: 1,
            ])
            guard newRecorder.record() else {
                throw TranscriptionError.process("Could not start recording.")
            }
            if let recordingURL { try? FileManager.default.removeItem(at: recordingURL) }
            recordingURL = url
            audioURL = url
            recorder = newRecorder
            resetAudioRange()
            image = nil
            draft = ""
            source = "Microphone recording"
            status = "Recording…"
        } catch {
            status = error.localizedDescription
        }
    }

    private func preview(_ url: URL) {
        if let player, player.isPlaying {
            player.stop()
            return
        }
        let clip = selectedClip
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

    private func readMedia() {
        let clip = selectedClip
        let projectPath = settings.projectPath
        let sourceLabel = sourceWithRange(clip)
        player?.stop()
        busy = true
        status = "Transcribing…"
        Task {
            var temporary: URL?
            defer {
                busy = false
                if let temporary { try? FileManager.default.removeItem(at: temporary) }
            }
            do {
                let command: String
                let input: URL
                if let image {
                    command = "ocr"
                    input = try writeCrop(image)
                    temporary = input
                } else if let audioURL {
                    command = "transcribe"
                    temporary = try await clip?.export(from: audioURL)
                    input = temporary ?? audioURL
                } else {
                    return
                }
                let result = try await Task.detached {
                    try runTranscription(projectPath, command, input, sourceLabel)
                }.value
                draft = result.text
                draftClip = clip
                status = draft.isEmpty ? "No text was detected. Select another region or type the phrase." : "Review the Japanese text before creating a card."
            } catch {
                status = error.localizedDescription
            }
        }
    }

    private func writeCrop(_ image: NSImage) throws -> URL {
        guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
            throw TranscriptionError.process("Could not decode the image.")
        }
        let output: CGImage
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
            output = cropped
        } else {
            output = cgImage
        }
        guard let png = NSBitmapImageRep(cgImage: output).representation(using: .png, properties: [:]) else {
            throw TranscriptionError.process("Could not encode the selected image.")
        }
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString).appendingPathExtension("png")
        try png.write(to: url, options: .atomic)
        return url
    }

    private func createCard() {
        var args = ["--deck-name", deckName, "-s", "ja", "-t", "en"]
        if includeAudio { args.append("--audio") }
        let label = sourceWithRange(draftClip)
        if !label.isEmpty { args += ["--source", label] }
        args += ["--", draft]
        runGeneration(projectPath: settings.projectPath, command: "add", args: args,
                      isGenerating: $busy, progressMessage: $status) { status = "" }
    }

    private func sourceWithRange(_ clip: AudioClip?) -> String {
        guard let clip else { return source }
        let label = source.isEmpty ? audioURL?.lastPathComponent ?? "Audio" : source
        return "\(label) [\(clip.timestampLabel)]"
    }
}

private func withAccess<T>(_ url: URL, action: () throws -> T) rethrows -> T {
    let accessed = url.startAccessingSecurityScopedResource()
    defer { if accessed { url.stopAccessingSecurityScopedResource() } }
    return try action()
}

private func runTranscription(
    _ projectPath: String, _ command: String, _ input: URL, _ source: String
) throws -> TranscriptionDraft {
    try withAccess(input) {
        let process = Process()
        let project = URL(fileURLWithPath: projectPath)
        process.executableURL = project.appendingPathComponent(".venv/bin/python")
        process.currentDirectoryURL = project
        process.arguments = [
            project.appendingPathComponent("infrastructure/cli/main.py").path,
            command, "--source", source, "--", input.path,
        ]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        try process.run()
        let output = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            throw TranscriptionError.process(output.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        for line in output.split(separator: "\n").reversed() {
            if let draft = try? JSONDecoder().decode(TranscriptionDraft.self, from: Data(line.utf8)) {
                return draft
            }
        }
        throw TranscriptionError.noDraft
    }
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
