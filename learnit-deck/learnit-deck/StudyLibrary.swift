import Foundation
import SwiftUI

struct StudyDeck: Decodable, Identifiable, Sendable {
    let id: Int64
    let name: String
    let description: String
    let cards: Int
    let due: Int
    let fresh: Int
}

struct StudyDay: Decodable, Identifiable, Sendable {
    var id: String { label }
    let label: String
    let reviews: Int
}

struct StudyPreferences: Decodable, Sendable {
    let newLimit: Int
    let autoAudio: Int
}

struct StudySummary: Decodable, Sendable {
    let decks: [StudyDeck]
    let days: [StudyDay]
    let scheduled: Int
    let preferences: StudyPreferences
    let history: Int

    static let empty = Self(decks: [], days: [], scheduled: 0,
                            preferences: StudyPreferences(newLimit: 20, autoAudio: 0), history: 0)
    var due: Int { decks.reduce(0) { $0 + $1.due } }
    var fresh: Int { decks.reduce(0) { $0 + $1.fresh } }
    var reviewed: Int { days.last?.reviews ?? 0 }
}

struct StudyImport: Decodable, Sendable {
    let decks: [String]
    let notes: Int
    let cards: Int
    let reviews: Int
    let media: Int
    let skipped: Int
    let added: Int?
}

struct StudyReadingCleanup: Decodable, Sendable, Identifiable {
    struct Example: Decodable, Sendable, Identifiable {
        let id: Int64
        let before: String
        let after: String
    }

    var id: String { token }
    let convertible: Int
    let needsReview: Int
    let noKanji: Int
    let examples: [Example]
    let token: String
}

struct StudyReadingCleanupResult: Decodable, Sendable {
    let updated: Int
    let backup: String?
    let needsReview: Int
}

struct StudyCardSummary: Decodable, Identifiable, Sendable {
    let id: Int64
    let deckId: Int64
    let expression: String
    let state: String
    let due: Double?
}

struct StudyBrowseResult: Decodable, Sendable {
    let cards: [StudyCardSummary]
}

struct StudyTrack: Decodable, Identifiable, Sendable {
    var id: String { label }
    let label: String
    let path: String
}

struct StudyCard: Decodable, Identifiable, Sendable {
    let id: Int64
    let deckId: Int64
    let state: String
    let due: Double?
    let revision: Int
    let expression: String
    let meaning: String
    let reading: String
    let audio: [StudyTrack]
    let frontHtml: String
    let backHtml: String
    let readingHtml: String
    let grades: [String]
    let dictionaryWords: [String]
    let meaningBody: String?
    let meaningBodyHtml: String?
}

struct StudyCardChanges: Encodable, Sendable {
    var expression: String
    var meaning: String
    var reading: String
    var headwords: String

    init(_ card: StudyCard) {
        expression = card.expression
        meaning = card.meaningBody ?? card.meaning
        reading = card.reading
        headwords = card.dictionaryWords.joined(separator: "、")
    }
}

struct StudyCardID: Decodable, Sendable {
    let id: Int64
}

struct StudyNextCard: Decodable, Sendable {
    let card: StudyCard?
    let nextDue: Double?
}

struct StudyGrade: Decodable, Sendable {
    let label: String
}

struct StudyBackup: Decodable, Sendable {
    let path: String
}

@MainActor
final class StudyLibrary: ObservableObject {
    let project: String
    let database: URL
    @Published private(set) var summary = StudySummary.empty
    @Published private(set) var ready = false
    @Published private(set) var revision = 0
    @Published var problem: String?

    init(project: String, database: URL? = nil) {
        self.project = project
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        self.database = database ?? support.appendingPathComponent("Learnit Study/Collection.sqlite3")
    }

    func load() async {
        do { try await refresh() }
        catch { problem = error.localizedDescription }
    }

    func refresh() async throws {
        summary = try await request(StudySummary.self, ["summary"])
        ready = true
    }

    func collectionChanged() async {
        revision += 1
        await load()
    }

    func request<Result: Decodable & Sendable>(_ type: Result.Type, _ arguments: [String],
                                               accessing input: URL? = nil) async throws -> Result {
        try await Self.request(type, project: project, database: database, arguments, accessing: input)
    }

    nonisolated static func request<Result: Decodable & Sendable>(
        _ type: Result.Type, project: String, database: URL, _ arguments: [String], accessing input: URL? = nil
    ) async throws -> Result {
        try await Task.detached(priority: .userInitiated) {
            let output = try AppCLI.run(project, command: "study", arguments: ["--database", database.path] + arguments,
                                        accessing: input)
            return try AppCLI.result(type, from: output, keys: .convertFromSnakeCase)
        }.value
    }
}
