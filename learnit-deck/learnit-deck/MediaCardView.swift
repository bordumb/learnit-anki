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
                    HStack {
                        Text(audioURL == recordingURL ? "Recording" : audioURL.lastPathComponent)
                            .lineLimit(1)
                        Button("Play or Stop") { play(audioURL) }
                        Button("Transcribe Audio") { readMedia() }
                    }
                    .disabled(busy || recorder != nil)
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
                }
                draft = ""
                status = ""
                source = url.lastPathComponent
            } catch {
                status = error.localizedDescription
            }
        }
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
            image = nil
            draft = ""
            source = "Microphone recording"
            status = "Recording…"
        } catch {
            status = error.localizedDescription
        }
    }

    private func play(_ url: URL) {
        if let player, player.isPlaying {
            player.stop()
            return
        }
        do {
            let data = try withAccess(url) { try Data(contentsOf: url) }
            let newPlayer = try AVAudioPlayer(data: data)
            player = newPlayer
            newPlayer.play()
        } catch {
            status = error.localizedDescription
        }
    }

    private func readMedia() {
        do {
            let command: String
            let input: URL
            let temporary: Bool
            if let image {
                command = "ocr"
                input = try writeCrop(image)
                temporary = true
            } else if let audioURL {
                command = "transcribe"
                input = audioURL
                temporary = false
            } else {
                return
            }
            let projectPath = settings.projectPath
            let sourceLabel = source
            busy = true
            status = "Transcribing…"
            Task {
                defer {
                    busy = false
                    if temporary { try? FileManager.default.removeItem(at: input) }
                }
                do {
                    let result = try await Task.detached {
                        try runTranscription(projectPath, command, input, sourceLabel)
                    }.value
                    draft = result.text
                    status = draft.isEmpty ? "No text was detected. Select another region or type the phrase." : "Review the Japanese text before creating a card."
                } catch {
                    status = error.localizedDescription
                }
            }
        } catch {
            status = error.localizedDescription
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
        if !source.isEmpty { args += ["--source", source] }
        args += ["--", draft]
        runGeneration(projectPath: settings.projectPath, command: "add", args: args,
                      isGenerating: $busy, progressMessage: $status) { status = "" }
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
