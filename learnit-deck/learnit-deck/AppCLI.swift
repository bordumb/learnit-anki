import Foundation

enum AppCLI {
    static func run(_ projectPath: String, command: String, arguments: [String],
                    accessing input: URL? = nil) throws -> String {
        let project = URL(fileURLWithPath: projectPath, isDirectory: true)
        let python = project.appendingPathComponent(".venv/bin/python")
        let script = project.appendingPathComponent("infrastructure/cli/main.py")
        guard FileManager.default.isExecutableFile(atPath: python.path),
              FileManager.default.fileExists(atPath: script.path) else {
            throw CLIError(message: "Check the Learnit project folder and Python environment in Settings.")
        }

        let accessed = input?.startAccessingSecurityScopedResource() ?? false
        defer { if accessed { input?.stopAccessingSecurityScopedResource() } }

        let process = Process()
        process.executableURL = python
        process.currentDirectoryURL = project
        let entry = command == "study" ? ["-m", "infrastructure.cli.study"] : [script.path, command]
        process.arguments = entry + arguments
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        try process.run()
        let output = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        process.waitUntilExit()
        guard process.terminationStatus == 0 else {
            if let failure = try? result(CLIFailure.self, from: output) {
                throw CLIError(message: failure.message, isTranslationFailure: failure.error == "translation")
            }
            let details = output.split(separator: "\n").last {
                $0.hasPrefix("Error:") || $0.hasPrefix("❌ Error")
            }
            throw CLIError(message: details.map(String.init) ?? output)
        }
        return output
    }

    static func result<Value: Decodable>(_ type: Value.Type, from output: String,
                                          keys: JSONDecoder.KeyDecodingStrategy = .useDefaultKeys) throws -> Value {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = keys
        for line in output.split(separator: "\n").reversed() {
            if let result = try? decoder.decode(type, from: Data(line.utf8)) {
                return result
            }
        }
        throw CLIError(message: "The command did not return a result.")
    }

    static func analyzePassage<Value: Decodable & Sendable>(_ type: Value.Type, project: String,
                                                            command: String, text: String) async throws -> Value {
        try await Task.detached(priority: .userInitiated) {
            let directory = FileManager.default.temporaryDirectory
                .appendingPathComponent(UUID().uuidString, isDirectory: true)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false,
                                                    attributes: [.posixPermissions: 0o700])
            defer { try? FileManager.default.removeItem(at: directory) }
            let file = directory.appendingPathComponent("passage.txt")
            try Data(text.utf8).write(to: file)
            let output = try run(project, command: command, arguments: ["--", file.path])
            return try result(type, from: output)
        }.value
    }
}

private struct CLIFailure: Decodable {
    let error: String
    let message: String
}

struct CLIError: LocalizedError {
    let message: String
    var isTranslationFailure = false

    var errorDescription: String? {
        message.isEmpty ? "The Learnit command failed." : message
    }
}
