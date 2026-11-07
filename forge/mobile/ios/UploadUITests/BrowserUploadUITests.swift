import XCTest

// Separate scheme: no skipping assertions or changing the ordinary keyboard
// suite when a local HTTPS fixture or simulator Files provider is unavailable.
final class BrowserUploadUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    private func attachState(_ app: XCUIApplication, _ label: String) {
        let hierarchy = XCTAttachment(string: app.debugDescription)
        hierarchy.name = label + "-hierarchy"
        hierarchy.lifetime = .keepAlways
        add(hierarchy)
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = label + "-screenshot"
        screenshot.lifetime = .keepAlways
        add(screenshot)
    }

    func testDefaultWebKitFilePanelCanBeOpenedAndCancelled() throws {
        let raw = try XCTUnwrap(ProcessInfo.processInfo.environment["FORGE_UPLOAD_FIXTURE_URL"])
        let url = try XCTUnwrap(URL(string: raw))
        XCTAssertEqual(url.scheme, "https")
        XCTAssertEqual(url.host, "127.0.0.1")
        XCTAssertEqual(url.path, "/form")
        XCTAssertEqual(url.query, "case=cancel")
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        defer { app.terminate() }
        let address = app.textFields["forge-address"]
        XCTAssertTrue(address.waitForExistence(timeout: 20))
        address.tap()
        address.typeText(raw + "\n")
        let choose = app.webViews.buttons["Choose fixture"]
        defer { attachState(app, "final-upload-state") }
        XCTAssertTrue(choose.waitForExistence(timeout: 30))
        choose.tap()
        attachState(app, "default-upload-menu")
        let files = app.buttons["Choose File"]
        XCTAssertTrue(files.waitForExistence(timeout: 10))
        files.tap()
        attachState(app, "system-file-panel")
        let picker = app.otherElements["Browse View (Picker)"]
        XCTAssertTrue(picker.waitForExistence(timeout: 20))
        let navigation = picker.navigationBars["FullDocumentManagerViewControllerNavigationBar"]
        XCTAssertTrue(navigation.exists)
        let cancel = navigation.buttons["Cancel"]
        XCTAssertTrue(cancel.exists)
        cancel.tap()
        XCTAssertTrue(app.webViews.staticTexts["No fixture selected"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.webViews.buttons["Submit fixture"].exists)
    }
}
