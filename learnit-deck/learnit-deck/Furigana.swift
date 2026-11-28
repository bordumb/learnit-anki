import SwiftUI

struct FuriganaSpan: Decodable, Sendable {
    let text: String
    var reading: String? = nil
    let editable: Bool
}

struct FuriganaDraft {
    let source: String
    var spans: [FuriganaSpan]
    var generationError: String? = nil

    static func generate(for source: String, project: String) async -> Self {
        do {
            let spans = try await AppCLI.analyzePassage([FuriganaSpan].self, project: project,
                                                        command: "furigana", text: source)
            guard spans.map(\.text).joined() == source else {
                throw CLIError(message: "Could not align the readings with this passage.")
            }
            return Self(source: source, spans: spans)
        } catch {
            return Self(source: source, spans: manualSpans(for: source), generationError: error.localizedDescription)
        }
    }

    static func manualSpans(for source: String) -> [FuriganaSpan] {
        var spans = [FuriganaSpan]()
        var buffer = ""
        var bufferIsEditable = false
        for character in source {
            let editable = character.unicodeScalars.contains { $0.properties.isIdeographic || "々〆〇".unicodeScalars.contains($0) }
            if !buffer.isEmpty, bufferIsEditable != editable {
                spans.append(FuriganaSpan(text: buffer, editable: bufferIsEditable))
                buffer = ""
            }
            buffer.append(character)
            bufferIsEditable = editable
        }
        if !buffer.isEmpty {
            spans.append(FuriganaSpan(text: buffer, editable: bufferIsEditable))
        }
        return spans
    }

    var ankiReading: String {
        guard spans.contains(where: { $0.reading != nil }) else { return "" }
        var result = ""
        for span in spans {
            if let reading = span.reading {
                // Anki uses whitespace to delimit the text covered by this ruby.
                if result.last?.isWhitespace == false { result += " " }
                result += "\(span.text)[\(reading)]"
            } else {
                result += span.text
            }
        }
        return result
    }
}

struct FuriganaEditor: View {
    @Binding var draft: FuriganaDraft
    @State private var selected: Selection?

    private struct Selection: Identifiable {
        let id: Int
    }

    var body: some View {
        FuriganaFlow {
            ForEach(draft.spans.indices, id: \.self) { index in
                let span = draft.spans[index]
                if span.editable {
                    Button {
                        selected = Selection(id: index)
                    } label: {
                        token(span.text, reading: span.reading)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Color.accentColor)
                    .accessibilityLabel("Edit reading for \(span.text)")
                    .accessibilityValue(span.reading ?? "No reading")
                } else {
                    let lines = span.text.components(separatedBy: "\n")
                    ForEach(lines.indices, id: \.self) { line in
                        if line > 0 {
                            Color.clear.frame(width: 0, height: 0)
                                .layoutValue(key: FuriganaLineBreak.self, value: true)
                                .accessibilityHidden(true)
                        }
                        if !lines[line].isEmpty { token(lines[line]) }
                    }
                }
            }
        }
        .popover(item: $selected) { selection in
            ReadingCorrection(index: selection.id, spans: draft.spans) { range, span in
                selected = nil
                draft.spans.replaceSubrange(range, with: [span])
            }
        }
    }

    private func token(_ text: String, reading: String? = nil) -> some View {
        VStack(spacing: 0) {
            Text(verbatim: reading ?? " ")
                .font(.caption)
                .accessibilityHidden(true)
            Text(verbatim: text)
                .font(.system(.title3, design: .serif))
        }
    }
}

private struct ReadingCorrection: View {
    let index: Int
    let spans: [FuriganaSpan]
    let save: (ClosedRange<Int>, FuriganaSpan) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var reading = ""
    @State private var end: Int?

    private var last: Int { end ?? index }
    private var expression: String { spans[index...last].map(\.text).joined() }
    private var canJoin: Bool {
        last + 1 < spans.count && spans[last + 1].editable
    }
    private var kana: String { reading.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var isValid: Bool {
        kana.unicodeScalars.allSatisfy { scalar in
            [0x3041...0x3096, 0x3099...0x309E, 0x30A1...0x30FA, 0x30FC...0x30FE]
                .contains { $0.contains(Int(scalar.value)) }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Reading for \(expression)").font(.headline)
            TextField("Kana reading", text: $reading).textFieldStyle(.roundedBorder)
            if canJoin {
                Button("Include \(spans[last + 1].text)") {
                    reading += spans[last + 1].reading ?? ""
                    end = last + 1
                }
                .buttonStyle(.link)
            }
            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button("Save reading") {
                    let span = FuriganaSpan(text: expression, reading: kana.isEmpty ? nil : kana, editable: true)
                    save(index...last, span)
                }
                .keyboardShortcut(.defaultAction)
                .disabled(!isValid || (last != index && kana.isEmpty))
            }
        }
        .padding(16)
        .frame(width: 280)
        .onAppear { reading = spans[index].reading ?? "" }
    }
}

private struct FuriganaLineBreak: LayoutValueKey {
    static let defaultValue = false
}

private struct FuriganaFlow: Layout {
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        arrange(width: proposal.width ?? .infinity, subviews: subviews).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let arrangement = arrange(width: bounds.width, subviews: subviews)
        for (subview, frame) in zip(subviews, arrangement.frames) {
            subview.place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY),
                          anchor: .topLeading, proposal: ProposedViewSize(frame.size))
        }
    }

    private func arrange(width: CGFloat, subviews: Subviews) -> (size: CGSize, frames: [CGRect]) {
        var x: CGFloat = 0
        var y: CGFloat = 0
        var lineHeight: CGFloat = 0
        var usedWidth: CGFloat = 0
        var frames: [CGRect] = []
        for view in subviews {
            if view[FuriganaLineBreak.self] {
                frames.append(.zero)
                y += max(36, lineHeight) + 3
                x = 0
                lineHeight = 0
                continue
            }
            let natural = view.sizeThatFits(.unspecified)
            let size = natural.width <= width ? natural : view.sizeThatFits(ProposedViewSize(width: width, height: nil))
            if x > 0 && x + size.width > width {
                y += lineHeight + 3
                x = 0
                lineHeight = 0
            }
            frames.append(CGRect(origin: CGPoint(x: x, y: y), size: size))
            x += size.width
            lineHeight = max(lineHeight, size.height)
            usedWidth = max(usedWidth, x)
        }
        return (CGSize(width: usedWidth, height: y + lineHeight), frames)
    }
}
