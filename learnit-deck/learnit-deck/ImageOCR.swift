import AppKit
import Vision

enum ImageOCR {
    static func readOnMac(_ image: CGImage) async throws -> String {
        try await Task.detached(priority: .userInitiated) {
            let request = VNRecognizeTextRequest()
            request.recognitionLevel = .accurate
            guard try request.supportedRecognitionLanguages().contains("ja-JP") else {
                throw ImageOCRError.unsupportedJapanese
            }
            request.recognitionLanguages = ["ja-JP"]
            do {
                try VNImageRequestHandler(cgImage: image, orientation: .up).perform([request])
            } catch {
                throw ImageOCRError.recognitionFailed
            }
            return (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
                .joined(separator: "\n")
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }.value
    }

    static func writeUploadImage(_ image: CGImage) throws -> URL {
        let bitmap = NSBitmapImageRep(cgImage: image)
        guard let png = bitmap.representation(using: .png, properties: [:]) else {
            throw ImageOCRError.encodingFailed
        }
        var data = png
        var fileExtension = "png"
        if png.count > 1_000_000, let jpeg = compressedPhoto(image), jpeg.count < png.count {
            data = jpeg
            fileExtension = "jpg"
        }

        let file = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            .appendingPathExtension(fileExtension)
        try data.write(to: file, options: .atomic)
        return file
    }

    private static func compressedPhoto(_ image: CGImage) -> Data? {
        // Use a white background for transparent images so dark strokes stay visible.
        guard let context = CGContext(data: nil, width: image.width, height: image.height,
                                      bitsPerComponent: 8, bytesPerRow: 0,
                                      space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
        let bounds = CGRect(x: 0, y: 0, width: image.width, height: image.height)
        context.setFillColor(gray: 1, alpha: 1)
        context.fill(bounds)
        context.draw(image, in: bounds)
        guard let opaqueImage = context.makeImage() else { return nil }
        return NSBitmapImageRep(cgImage: opaqueImage)
            .representation(using: .jpeg, properties: [.compressionFactor: 0.9])
    }
}

private enum ImageOCRError: LocalizedError {
    case unsupportedJapanese
    case encodingFailed
    case recognitionFailed

    var errorDescription: String? {
        switch self {
        case .unsupportedJapanese: return "Japanese text recognition is unavailable on this Mac."
        case .encodingFailed: return "Could not encode the selected image."
        case .recognitionFailed: return "Apple Vision could not read the image on this Mac. Try Read with Google or enter the text manually."
        }
    }
}
