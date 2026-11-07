import XCTest

final class BrowserTabsUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    private var russian: Bool { ProcessInfo.processInfo.environment["FORGE_UI_TEST_LANGUAGE"] == "ru" }

    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-AppleLanguages", russian ? "(ru)" : "(en)",
            "-AppleLocale", russian ? "ru_RU" : "en_US"]
        app.launch()
        return app
    }

    private func openTabs(_ app: XCUIApplication) -> XCUIElement {
        app.buttons["forge-tabs"].tap()
        let list = app.tables["forge-tabs-list"]
        XCTAssertTrue(list.waitForExistence(timeout: 10))
        return list
    }

    func testAddAndCloseTabFromOverviewKeepsOtherTabs() {
        let app = launch()
        defer { app.terminate() }
        let list = openTabs(app)
        let before = list.cells.count
        app.buttons["forge-tabs-add"].tap()
        XCTAssertTrue(app.textFields["forge-address"].waitForExistence(timeout: 10))
        let updated = openTabs(app)
        XCTAssertEqual(updated.cells.count, before + 1)
        let close = updated.cells.element(boundBy: before).buttons.matching(
            NSPredicate(format: "identifier BEGINSWITH %@", "forge-tab-close-")).firstMatch
        XCTAssertTrue(close.exists)
        close.tap()
        XCTAssertEqual(updated.cells.count, before)
        app.buttons["forge-tabs-done"].tap()
        XCTAssertTrue(app.textFields["forge-address"].waitForExistence(timeout: 10))
    }

    func testSearchAndPrivateModeDoNotMixGroupRows() {
        let app = launch()
        defer { app.terminate() }
        _ = openTabs(app)
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 10))
        search.tap()
        search.typeText("forge-no-matching-tab-fixture")
        XCTAssertTrue(app.staticTexts["forge-tabs-empty"].waitForExistence(timeout: 5))
        app.tables["forge-tabs-list"].buttons[russian ? "Приватные вкладки" : "Private tabs"].tap()
        let snapshot = XCTAttachment(screenshot: app.screenshot())
        snapshot.name = "tabs-after-private-switch"
        snapshot.lifetime = .keepAlways
        add(snapshot)
        let hierarchy = XCTAttachment(string: app.debugDescription)
        hierarchy.name = "tabs-after-private-switch-hierarchy"
        hierarchy.lifetime = .keepAlways
        add(hierarchy)
        XCTAssertFalse(app.staticTexts["forge-tabs-empty"].exists)
        XCTAssertTrue(app.buttons["forge-tabs-close-private"].waitForExistence(timeout: 5))
        app.buttons["forge-tabs-close-private"].tap()
        let title = russian ? "Закрыть все приватные вкладки" : "Close all private tabs"
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 5))
        app.alerts.buttons[title].tap()
        // A tap finishing is not proof that UIKit has finished removing its
        // navigation item from the accessibility tree during alert dismissal.
        let closePrivate = app.buttons["forge-tabs-close-private"]
        let closed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: closePrivate)
        let regular = app.tables["forge-tabs-list"].buttons[russian ? "Обычные вкладки" : "Regular tabs"]
        let regularSelected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "selected == true"), object: regular)
        wait(for: [closed, regularSelected], timeout: 5)
        XCTAssertFalse(app.buttons["forge-tabs-close-private"].exists)
        app.buttons["forge-tabs-done"].tap()
        XCTAssertTrue(app.textFields["forge-address"].waitForExistence(timeout: 10))
    }

    func testBrowserMenuOpensOverviewWithoutChangingSelectedAddress() {
        let app = launch()
        defer { app.terminate() }
        let address = app.textFields["forge-address"]
        XCTAssertTrue(address.waitForExistence(timeout: 15))
        let before = address.value as? String
        app.buttons["forge-menu"].tap()
        app.buttons[russian ? "Вкладки" : "Tabs"].tap()
        XCTAssertTrue(app.tables["forge-tabs-list"].waitForExistence(timeout: 10))
        app.buttons["forge-tabs-done"].tap()
        XCTAssertTrue(address.waitForExistence(timeout: 10))
        XCTAssertEqual(address.value as? String, before)
    }

    func testSelectingSearchResultClosesEntireOverview() {
        let app = launch()
        defer { app.terminate() }
        _ = openTabs(app)
        let search = app.searchFields.firstMatch
        search.tap()
        search.typeText("about:blank")
        let row = app.tables["forge-tabs-list"].cells.firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.textFields["forge-address"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.tables["forge-tabs-list"].exists)
    }

    func testBlankTabMenuDoesNotOfferSharingOrPageSearch() {
        let app = launch()
        defer { app.terminate() }
        XCTAssertTrue(app.buttons["forge-new-tab"].waitForExistence(timeout: 15))
        app.buttons["forge-new-tab"].tap()
        app.buttons["forge-menu"].tap()
        let share = app.buttons[russian ? "Поделиться ссылкой" : "Share link"]
        let find = app.buttons[russian ? "Найти на странице" : "Find in page"]
        XCTAssertTrue(share.waitForExistence(timeout: 5))
        XCTAssertFalse(share.isEnabled)
        XCTAssertFalse(find.isEnabled)
        // UIKit presents this action sheet as a popover on some size classes;
        // there is no separate Cancel button in that presentation.
        app.sheets.buttons[russian ? "Вкладки" : "Tabs"].tap()
        let list = app.tables["forge-tabs-list"]
        XCTAssertTrue(list.waitForExistence(timeout: 10))
        let close = list.cells.element(boundBy: list.cells.count - 1).buttons.matching(
            NSPredicate(format: "identifier BEGINSWITH %@", "forge-tab-close-")).firstMatch
        close.tap()
        app.buttons["forge-tabs-done"].tap()
    }

    func testLibraryMenuAndSearchDoNotNavigateOnOpen() {
        let app = launch()
        defer { app.terminate() }
        let address = app.textFields["forge-address"]
        XCTAssertTrue(address.waitForExistence(timeout: 15))
        let before = address.value as? String
        app.buttons["forge-menu"].tap()
        app.sheets.buttons[russian ? "Закладки" : "Bookmarks"].tap()
        let list = app.tables["forge-library-list"]
        XCTAssertTrue(list.waitForExistence(timeout: 10))
        let search = app.searchFields.firstMatch
        search.tap(); search.typeText("forge-library-no-match-fixture")
        XCTAssertTrue(app.staticTexts["forge-library-empty"].waitForExistence(timeout: 5))
        list.buttons[russian ? "История" : "History"].tap()
        XCTAssertTrue(app.buttons["forge-library-clear-history"].exists)
        app.buttons["forge-library-done"].tap()
        XCTAssertTrue(address.waitForExistence(timeout: 10))
        XCTAssertEqual(address.value as? String, before)
    }
}
