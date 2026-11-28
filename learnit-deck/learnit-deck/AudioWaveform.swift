import AVFoundation
import SwiftUI

enum AudioWaveform {
    static func peaks(of url: URL) async -> [Float] {
        await Task.detached(priority: .utility) {
            let accessed = url.startAccessingSecurityScopedResource()
            defer { if accessed { url.stopAccessingSecurityScopedResource() } }
            let original = readPeaks(of: url)
            if !original.isEmpty { return original }
            guard let ffmpeg = AudioClip.audioTool("ffmpeg") else { return [] }
            let wave = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString).appendingPathExtension("wav")
            defer { try? FileManager.default.removeItem(at: wave) }
            do {
                _ = try AudioClip.run(ffmpeg, [
                    "-nostdin", "-loglevel", "error", "-i", url.path, "-vn",
                    "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", wave.path,
                ])
                return readPeaks(of: wave)
            } catch {
                return []
            }
        }.value
    }

    private static func readPeaks(of url: URL) -> [Float] {
        guard let audio = try? AVAudioFile(forReading: url), audio.length > 0,
              let buffer = AVAudioPCMBuffer(pcmFormat: audio.processingFormat, frameCapacity: 8192)
        else { return [] }
        let count = min(130, Int(audio.length))
        let framesPerBar = (audio.length - 1) / Int64(count) + 1
        var framesLeft = audio.length
        var peaks: [Float] = []
        for _ in 0..<count {
            let framesInBar = min(framesPerBar, framesLeft)
            var remaining = framesInBar
            var peak: Float = 0
            while remaining > 0 {
                let frames = AVAudioFrameCount(min(remaining, Int64(buffer.frameCapacity)))
                do { try audio.read(into: buffer, frameCount: frames) }
                catch { return [] }
                guard buffer.frameLength > 0 else { break }
                guard let channels = buffer.floatChannelData else { return [] }
                for channel in 0..<Int(buffer.format.channelCount) {
                    for frame in stride(from: 0, to: Int(buffer.frameLength), by: 4) {
                        peak = max(peak, abs(channels[channel][frame]))
                    }
                }
                remaining -= Int64(buffer.frameLength)
                framesLeft -= Int64(buffer.frameLength)
            }
            guard remaining < framesInBar else { break }
            peaks.append(peak)
        }
        let loudest = peaks.max() ?? 0
        return loudest > 0 ? peaks.map { $0 / loudest } : peaks
    }
}

struct AudioWaveformView: View {
    let peaks: [Float]
    let duration: TimeInterval
    let trimming: Bool
    @Binding var start: TimeInterval
    @Binding var end: TimeInterval

    var body: some View {
        GeometryReader { geometry in
            let width = geometry.size.width
            let left = position(start, width: width)
            let right = position(end, width: width)
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 8).fill(.quaternary.opacity(0.4))
                if trimming && right > left {
                    Rectangle().fill(Color.accentColor.opacity(0.15))
                        .frame(width: right - left)
                        .offset(x: left)
                }
                Canvas { context, size in
                    let spacing = size.width / CGFloat(max(peaks.count, 1))
                    for (index, peak) in peaks.enumerated() {
                        let x = (CGFloat(index) + 0.5) * spacing
                        let height = max(2, CGFloat(peak) * size.height * 0.74)
                        let bar = CGRect(x: x - spacing * 0.25, y: (size.height - height) / 2,
                                         width: spacing * 0.5, height: height)
                        let selected = trimming && x >= left && x <= right
                        context.fill(Path(roundedRect: bar, cornerRadius: 2),
                                     with: .color(selected ? .accentColor : .secondary))
                    }
                }
                if trimming {
                    handle(at: left, width: width) { start = min($0, max(0, end - 0.01)) }
                    handle(at: right, width: width) { end = max($0, min(duration, start + 0.01)) }
                }
            }
            .coordinateSpace(name: "waveform")
        }
        .frame(height: 92)
        .accessibilityHidden(true)
    }

    private func position(_ time: TimeInterval, width: CGFloat) -> CGFloat {
        guard time.isFinite, duration > 0 else { return 0 }
        return width * min(1, max(0, time / duration))
    }

    private func handle(at position: CGFloat, width: CGFloat, change: @escaping (TimeInterval) -> Void) -> some View {
        Capsule()
            .fill(Color.accentColor)
            .frame(width: 8, height: 54)
            .frame(width: 24, height: 76)
            .contentShape(Rectangle())
            .offset(x: min(max(0, position - 12), max(0, width - 24)))
            .gesture(DragGesture(coordinateSpace: .named("waveform")).onChanged { event in
                guard width > 0 else { return }
                change(duration * min(1, max(0, event.location.x / width)))
            })
    }
}
