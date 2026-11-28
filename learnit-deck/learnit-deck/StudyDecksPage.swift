import Charts
import SwiftUI

struct StudyDecksPage: View {
    let summary: StudySummary
    let create: () -> Void
    let study: (Int64?) -> Void
    let browse: (Int64?) -> Void
    @State private var picked: Int64?

    var body: some View {
        StudyPageLayout("Decks", subtitle: "Choose what to study or browse your saved passages.") {
            HStack {
                Button("New deck", systemImage: "plus", action: create).buttonStyle(.borderedProminent)
                Button("Browse all cards") { browse(nil) }
            }
            if summary.decks.isEmpty {
                ContentUnavailableView("No decks yet", systemImage: "rectangle.stack",
                                       description: Text("Create a deck or import an Anki package from Today."))
            } else {
                HStack(alignment: .top, spacing: 16) {
                    StudyPanel {
                        Grid(alignment: .leading, horizontalSpacing: 20, verticalSpacing: 13) {
                            GridRow {
                                Text("Deck")
                                Text("Due")
                                Text("New")
                                Text("Cards")
                            }.foregroundStyle(.secondary).font(.subheadline)
                            ForEach(summary.decks) { deck in
                                Divider().gridCellColumns(4)
                                GridRow {
                                    Button(deck.name) { picked = deck.id }.buttonStyle(.link)
                                    Text(deck.due.formatted()).monospacedDigit()
                                    Text(deck.fresh.formatted()).monospacedDigit()
                                    Text(deck.cards.formatted()).monospacedDigit()
                                }
                            }
                        }
                    }
                    if let deck = summary.decks.first(where: { $0.id == picked }) ?? summary.decks.first {
                        StudyPanel {
                            VStack(alignment: .leading, spacing: 13) {
                                Text(deck.name).font(.title3.weight(.semibold))
                                if !deck.description.isEmpty { Text(deck.description).foregroundStyle(.secondary) }
                                HStack {
                                    Button("Study deck") { study(deck.id) }.buttonStyle(.borderedProminent)
                                    Button("Browse cards") { browse(deck.id) }
                                }
                            }
                        }.frame(maxWidth: 325)
                    }
                }
            }
        }
    }
}

struct StudyProgressPage: View {
    let summary: StudySummary

    var body: some View {
        StudyPageLayout("Progress", subtitle: "See your study activity and upcoming reviews.") {
            HStack(spacing: 12) {
                StudyStat("Reviews this week", value: summary.days.reduce(0) { $0 + $1.reviews })
                StudyStat("Reviewed today", value: summary.reviewed)
                StudyStat("Scheduled later", value: summary.scheduled)
            }
            StudyPanel {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Reviews by day").font(.headline)
                    Chart(summary.days) {
                        BarMark(x: .value("Day", String($0.label.suffix(5))), y: .value("Reviews", $0.reviews))
                            .foregroundStyle(Color.accentColor)
                    }.frame(height: 180)
                }
            }
            StudyPanel {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Due by deck").font(.headline)
                    ForEach(summary.decks) { deck in
                        HStack { Text(deck.name); Spacer(); Text("\(deck.due.formatted()) due").foregroundStyle(.secondary) }
                    }
                    Text("\(summary.history.formatted()) total review records")
                        .foregroundStyle(.secondary).font(.caption)
                }
            }
        }
    }
}
