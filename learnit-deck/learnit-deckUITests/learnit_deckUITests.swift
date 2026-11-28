//
//  learnit_deckUITests.swift
//  learnit-deckUITests
//
//  Created by bordumb on 20/10/2025.
//

import XCTest

final class learnit_deckUITests: XCTestCase {

    @MainActor
    private func launch(_ extraArguments: [String] = []) throws -> XCUIApplication {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false)
        addTeardownBlock { try? FileManager.default.removeItem(at: folder) }
        let repository = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let app = XCUIApplication()
        app.launchArguments = ["-projectPath", repository.path, "-studyTestDatabase", folder.appendingPathComponent("Study.sqlite3").path]
            + extraArguments
        app.launch()
        return app
    }

    @MainActor
    private func openAnkiExport(_ app: XCUIApplication) {
        let menu = app.menuBars.menuBarItems["File"]
        XCTAssertTrue(menu.waitForExistence(timeout: 5))
        menu.click()
        menu.menuItems["Anki Export Window"].click()
    }

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.

        // In UI tests it is usually best to stop immediately when a failure occurs.
        continueAfterFailure = false

        // In UI tests it’s important to set the initial state - such as interface orientation - required for your tests before they run. The setUp method is a good place to do this.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    @MainActor
    func testCardEditorAndMediaControlsShareOneWindow() throws {
        let app = try launch(["-passageTemplatePath", "standard"])
        openAnkiExport(app)

        let editor = app.textViews["Card text"]
        XCTAssertTrue(editor.waitForExistence(timeout: 5))
        let sources = app.descendants(matching: .any).matching(identifier: "Add source").firstMatch
        XCTAssertTrue(sources.exists)
        XCTAssertTrue(app.checkBoxes["Pronunciation audio"].exists)

        let create = app.buttons["Create card"]
        XCTAssertFalse(create.isEnabled)
        editor.click()
        editor.typeText("Hello")
        XCTAssertTrue(create.isEnabled)
    }

    @MainActor
    func testWholePassageAndDictionaryEntriesAppearTogetherInPreview() throws {
        let repository = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let reference = repository.appendingPathComponent("output/nihongo-deck-repaired.apkg")
        try XCTSkipUnless(FileManager.default.fileExists(atPath: reference.path))
        let app = try launch(["-passageTemplatePath", reference.path])
        openAnkiExport(app)

        let passage = app.textViews["Passage"]
        XCTAssertTrue(passage.waitForExistence(timeout: 12))
        let furigana = app.buttons["Furigana"]
        XCTAssertTrue(furigana.exists)
        XCTAssertFalse(furigana.isEnabled)
        passage.click()
        passage.typeText("First sentence. Second sentence.")
        furigana.click()
        let export = app.buttons["Export to Anki"]
        XCTAssertTrue(export.waitForExistence(timeout: 5))
        XCTAssertFalse(export.isEnabled)
        app.buttons["Back to draft"].click()
        let entries = app.textViews["Japanese dictionary entries"]
        XCTAssertTrue(entries.waitForExistence(timeout: 5))
        entries.click()
        entries.typeText("Dictionary definition")
        app.buttons["Preview card"].click()
        XCTAssertTrue(app.staticTexts["First sentence. Second sentence."].firstMatch.exists)
        XCTAssertTrue(app.staticTexts["Dictionary definition"].exists)
        XCTAssertTrue(export.exists)
    }

    @MainActor
    func testStudyWorkspaceCreatesAndReviewsCard() throws {
        let app = try launch()
        XCTAssertTrue(app.buttons["Import from Anki"].waitForExistence(timeout: 12))
        app.buttons["New deck"].click()
        let name = app.textFields["Name"]
        XCTAssertTrue(name.waitForExistence(timeout: 5))
        name.typeText("Reading notes")
        app.buttons["Create deck"].click()
        app.buttons["New card"].click()
        let passage = app.textViews["Passage"]
        XCTAssertTrue(passage.waitForExistence(timeout: 5))
        passage.click()
        passage.typeText("First sentence. Second sentence.")
        let meaning = app.textViews["Japanese dictionary entries"]
        meaning.click()
        meaning.typeText("A dictionary definition")
        app.buttons["Preview card"].click()
        let save = app.buttons["Save card"]
        XCTAssertTrue(save.waitForExistence(timeout: 5))
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "enabled == true"), object: save)
        XCTAssertEqual(XCTWaiter.wait(for: [ready], timeout: 5), .completed)
        save.click()
        XCTAssertTrue(app.staticTexts["Card saved."].waitForExistence(timeout: 5))
        app.staticTexts["Review"].firstMatch.click()
        XCTAssertTrue(app.buttons["Show answer"].waitForExistence(timeout: 10))
        app.buttons["Show answer"].click()
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Good'")).firstMatch.click()
        XCTAssertTrue(app.staticTexts["Session complete"].waitForExistence(timeout: 10))
    }

    @MainActor
    func testLaunchPerformance() throws {
        if #available(macOS 10.15, iOS 13.0, tvOS 13.0, watchOS 7.0, *) {
            // This measures how long it takes to launch your application.
            measure(metrics: [XCTApplicationLaunchMetric()]) {
                XCUIApplication().launch()
            }
        }
    }
}
