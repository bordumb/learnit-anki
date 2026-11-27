import AVFoundation

struct AudioClip: Sendable {
    let start: TimeInterval
    let end: TimeInterval

    init?(start: TimeInterval, end: TimeInterval, duration: TimeInterval) {
        guard start.isFinite, end.isFinite, duration.isFinite,
              start >= 0, end > start, end <= duration else { return nil }
        self.start = start
        self.end = end
    }

    var timestampLabel: String {
        "\(Self.timestamp(start))–\(Self.timestamp(end))"
    }

    static func timestamp(_ seconds: TimeInterval) -> String {
        guard seconds.isFinite, seconds >= 0, seconds < Double(Int.max) / 10 else { return "–" }
        let tenths = Int((seconds * 10).rounded())
        return String(format: "%d:%02d.%d", tenths / 600, (tenths / 10) % 60, tenths % 10)
    }

    static func duration(of input: URL) async -> TimeInterval? {
        await Task.detached { () -> TimeInterval? in
            let accessed = input.startAccessingSecurityScopedResource()
            defer { if accessed { input.stopAccessingSecurityScopedResource() } }

            if let original = try? AVAudioFile(forReading: input), original.length > 0 {
                return Double(original.length) / original.processingFormat.sampleRate
            }
            guard let ffprobe = audioTool("ffprobe"), let result = try? run(ffprobe, [
                "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", input.path,
            ]) else { return nil }
            return Double(result)
        }.value
    }

    func export(from input: URL) async throws -> URL {
        try await Task.detached(priority: .userInitiated) {
            try writeWave(from: input)
        }.value
    }

    private func writeWave(from input: URL) throws -> URL {
        let accessed = input.startAccessingSecurityScopedResource()
        defer { if accessed { input.stopAccessingSecurityScopedResource() } }

        let original = try? AVAudioFile(forReading: input)
        let output = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString).appendingPathExtension("wav")
        do {
            if let original, original.isLinearPCM {
                try writeNativeWave(from: original, to: output)
            } else if let ffmpeg = Self.audioTool("ffmpeg") {
                _ = try Self.run(ffmpeg, [
                    "-nostdin", "-loglevel", "error", "-ss", String(start), "-i", input.path,
                    "-t", String(end - start), "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", output.path,
                ])
                guard let clipped = try? AVAudioFile(forReading: output), clipped.length > 0 else {
                    throw AudioClipError.exportFailed("The selected segment contains no audio samples.")
                }
            } else if let original {
                try writeNativeWave(from: original, to: output)
            } else {
                throw AudioClipError.exportFailed("macOS could not decode the file. Install FFmpeg to trim this format.")
            }
            return output
        } catch {
            try? FileManager.default.removeItem(at: output)
            throw error
        }
    }

    private func writeNativeWave(from original: AVAudioFile, to output: URL) throws {
        let format = original.processingFormat
        let firstFrame = AVAudioFramePosition((start * format.sampleRate).rounded(.down))
        let lastFrame = min(original.length, AVAudioFramePosition((end * format.sampleRate).rounded(.up)))
        guard firstFrame < lastFrame else {
            throw AudioClipError.exportFailed("The selected segment contains no audio samples.")
        }
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: format.sampleRate,
            AVNumberOfChannelsKey: format.channelCount,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
        ]
        let clipped = try AVAudioFile(forWriting: output, settings: settings)
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 8192) else {
            throw AudioClipError.exportFailed("Could not allocate a buffer for the audio segment.")
        }
        if original.isLinearPCM {
            original.framePosition = firstFrame
        } else {
            var skipped: AVAudioFramePosition = 0
            while skipped < firstFrame {
                skipped += try readFrames(from: original, into: buffer, upTo: firstFrame - skipped)
            }
        }
        var remaining = lastFrame - firstFrame
        while remaining > 0 {
            remaining -= try readFrames(from: original, into: buffer, upTo: remaining)
            try clipped.write(from: buffer)
        }
    }

    private func readFrames(from file: AVAudioFile, into buffer: AVAudioPCMBuffer,
                            upTo remaining: AVAudioFramePosition) throws -> AVAudioFramePosition {
        let count = AVAudioFrameCount(min(remaining, Int64(buffer.frameCapacity)))
        try file.read(into: buffer, frameCount: count)
        guard buffer.frameLength > 0 else {
            throw AudioClipError.exportFailed("The recording ended before the selected segment was read.")
        }
        return Int64(buffer.frameLength)
    }

    private static func audioTool(_ name: String) -> URL? {
        let path = ProcessInfo.processInfo.environment["PATH"] ?? ""
        let directories = path.split(separator: ":").map(String.init) + ["/opt/homebrew/bin", "/usr/local/bin"]
        return directories.lazy.map { URL(fileURLWithPath: $0).appendingPathComponent(name) }
            .first { FileManager.default.isExecutableFile(atPath: $0.path) }
    }

    private static func run(_ command: URL, _ arguments: [String]) throws -> String {
        let process = Process()
        process.executableURL = command
        process.arguments = arguments
        let output = Pipe()
        process.standardOutput = output
        process.standardError = output
        try process.run()
        let result = String(decoding: output.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        process.waitUntilExit()
        guard process.terminationStatus == 0 else { throw AudioClipError.exportFailed(result) }
        return result
    }
}

private extension AVAudioFile {
    var isLinearPCM: Bool { fileFormat.streamDescription.pointee.mFormatID == kAudioFormatLinearPCM }
}

private enum AudioClipError: LocalizedError {
    case exportFailed(String)

    var errorDescription: String? {
        switch self {
        case .exportFailed(let reason): return reason.isEmpty ? "Could not export the selected audio segment." : reason
        }
    }
}
