import AVFoundation
import XCTest
@testable import learnit_deck

final class AudioClipTests: XCTestCase {
    func testRejectsInvalidRanges() {
        XCTAssertNil(AudioClip(start: -1, end: 3, duration: 10))
        XCTAssertNil(AudioClip(start: 2, end: 2, duration: 10))
        XCTAssertNil(AudioClip(start: 2, end: 11, duration: 10))
        XCTAssertNil(AudioClip(start: .nan, end: 5, duration: 10))
    }

    func testPodcastAndConversationExcerpts() async throws {
        let fixtures = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("data/golden/ja/audio/passages")
        for name in ["ja-gov-online-podcast-pets-qa.mp3", "ingcrowd-japanese-themed-dialogue01-extended.wav"] {
            let input = fixtures.appendingPathComponent(name)
            let measuredDuration = await AudioClip.duration(of: input)
            let duration = try XCTUnwrap(measuredDuration)
            let clip = try XCTUnwrap(AudioClip(start: 12.5, end: 19.3, duration: duration))
            XCTAssertEqual(clip.timestampLabel, "0:12.5–0:19.3")
            let output = try await clip.export(from: input)
            defer { try? FileManager.default.removeItem(at: output) }
            let audio = try AVAudioFile(forReading: output)
            let rate = audio.processingFormat.sampleRate
            XCTAssertEqual(Double(audio.length) / rate, 6.8, accuracy: 2 / rate)
        }
    }
}
