import XCTest

final class BrowserKeyboardUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    private var language: String {
        if let requested = ProcessInfo.processInfo.environment["FORGE_UI_TEST_LANGUAGE"], ["en", "ru"].contains(requested) { return requested }
        return Locale.preferredLanguages.first?.hasPrefix("ru") == true ? "ru" : "en"
    }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(\(language))", "-AppleLocale", language == "ru" ? "ru_RU" : "en_US"]
        app.launch()
        return app
    }

    func testAddressTapKeepsTypedTextAndDockAboveKeyboard() {
        let app = launch()
        defer { app.terminate() }
        let address = app.textFields["forge-address"]
        XCTAssertTrue(address.waitForExistence(timeout: 20))
        XCTAssertEqual(address.label, language == "ru" ? "Адрес или поиск" : "Address or search")
        address.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 15))
        address.typeText("keyboard-focus.invalid")
        XCTAssertEqual(address.value as? String, "keyboard-focus.invalid")
        XCTAssertLessThanOrEqual(address.frame.maxY, app.keyboards.firstMatch.frame.minY + 1)
        XCTAssertTrue(app.keyboards.firstMatch.exists)
    }

    func testStartSearchTapKeepsTypedTextWithoutSubmittingSearch() {
        let app = launch()
        defer { app.terminate() }
        let search = app.buttons["forge-start-search"]
        XCTAssertTrue(search.waitForExistence(timeout: 20))
        search.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 15))
        let address = app.textFields["forge-address"]
        address.typeText("search focus fixture")
        XCTAssertEqual(address.value as? String, "search focus fixture")
        XCTAssertTrue(app.keyboards.firstMatch.exists)
        XCTAssertLessThanOrEqual(address.frame.maxY, app.keyboards.firstMatch.frame.minY + 1)
    }

    func testCancelAddressEditingRestoresValueWithoutSubmittingNavigation() {
        let app = launch()
        defer { app.terminate() }
        let address = app.textFields["forge-address"]
        XCTAssertTrue(address.waitForExistence(timeout: 20))
        let before = address.value as? String
        address.tap()
        address.typeText("https://draft.invalid/not-submitted")
        let cancel = app.buttons["forge-address-cancel"]
        XCTAssertEqual(cancel.label, language == "ru" ? "Отменить ввод адреса" : "Cancel address editing")
        cancel.tap()
        XCTAssertTrue(app.buttons["forge-go"].waitForExistence(timeout: 10))
        XCTAssertEqual(address.value as? String, before)
        XCTAssertTrue(app.buttons["forge-reload"].exists)
        XCTAssertTrue(app.otherElements["forge-start"].exists)
    }
}
