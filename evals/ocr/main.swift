import AppKit
import Foundation
import Vision

struct Prediction: Encodable {
    let status: String
    let prediction: String
    let latency_seconds: Double
    let error_class: String?
}

if CommandLine.arguments.dropFirst().first == "--revision" {
    let request = VNRecognizeTextRequest()
    print(request.revision)
} else {
    let encoder = JSONEncoder()
    // Vision can emit system diagnostics on stdout. Give JSON its own stream.
    let results = FileHandle(fileDescriptor: dup(STDOUT_FILENO), closeOnDealloc: true)
    guard results.fileDescriptor >= 0, dup2(STDERR_FILENO, STDOUT_FILENO) >= 0 else {
        throw CocoaError(.fileWriteUnknown)
    }
    while let path = readLine() {
        let start = ProcessInfo.processInfo.systemUptime
        let row: Prediction
        do {
            guard let image = NSImage(contentsOfFile: path),
                  let raster = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
                throw CocoaError(.fileReadCorruptFile)
            }
            let text = try await ImageOCR.readOnMac(raster)
            row = Prediction(status: text.isEmpty ? "empty" : "ok", prediction: text,
                             latency_seconds: ProcessInfo.processInfo.systemUptime - start,
                             error_class: nil)
        } catch {
            row = Prediction(status: "provider_error", prediction: "",
                             latency_seconds: ProcessInfo.processInfo.systemUptime - start,
                             error_class: String(describing: type(of: error)))
        }
        try results.write(contentsOf: encoder.encode(row) + Data([0x0a]))
    }
}
