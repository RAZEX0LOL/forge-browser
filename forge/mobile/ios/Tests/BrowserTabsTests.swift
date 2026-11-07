import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserTabsTests: XCTestCase {
    func testSearchMatchesTitleAndAddressWithoutChangingSelection() {
        let first = BrowserTab(url: "https://example.invalid/docs", title: "Документация")
        let second = BrowserTab(url: "https://other.invalid/", title: "Other")
        let snapshot = BrowserTabsSnapshot(tabs: [first, second], selectedID: second.id, isPrivate: false)
        XCTAssertEqual(snapshot.matching(" ДОКУМЕНТАЦИЯ "), [first])
        XCTAssertEqual(snapshot.matching("EXAMPLE.INVALID"), [first])
        XCTAssertEqual(snapshot.matching("missing"), [])
        XCTAssertEqual(snapshot.matching("  "), [first, second])
        XCTAssertEqual(snapshot.selectedID, second.id)
    }

    func testOverviewCloseUsesStableIDWithoutSelectingAndKeepsLastBlankTab() throws {
        var session = BrowserSession()
        let first = session.selectedID
        let second = try XCTUnwrap(session.addTab())
        var selected = false
        let overview = BrowserTabsController(snapshot: {
            BrowserTabsSnapshot(tabs: session.tabs, selectedID: session.selectedID, isPrivate: false)
        }, select: { _ in selected = true }, close: { session.close($0) }, addTab: {}, changeMode: { _ in }, closePrivate: {})
        overview.loadViewIfNeeded()
        let row = overview.tableView(overview.tableView, cellForRowAt: IndexPath(row: 0, section: 0))
        let button = try XCTUnwrap(row.accessoryView as? UIButton)
        XCTAssertEqual(button.accessibilityIdentifier, "forge-tab-close-" + first.uuidString)
        button.sendActions(for: .touchUpInside)
        XCTAssertFalse(selected)
        XCTAssertEqual(session.selectedID, second)
        XCTAssertEqual(overview.tableView(overview.tableView, numberOfRowsInSection: 0), 1)
        let last = overview.tableView(overview.tableView, cellForRowAt: IndexPath(row: 0, section: 0))
        try XCTUnwrap(last.accessoryView as? UIButton).sendActions(for: .touchUpInside)
        XCTAssertEqual(session.tabs.count, 1)
        XCTAssertEqual(session.selectedTab.url, "about:blank")
        XCTAssertFalse(selected)
    }

    func testOverviewSearchIsScopedToCurrentGroupAndResetsOnModeSwitch() throws {
        let regular = BrowserTab(url: "https://regular.invalid", title: "Regular document")
        let secret = BrowserTab(url: "https://private.invalid", title: "Secret document")
        var privateMode = false
        let overview = BrowserTabsController(snapshot: {
            BrowserTabsSnapshot(tabs: privateMode ? [secret] : [regular],
                selectedID: privateMode ? secret.id : regular.id, isPrivate: privateMode)
        }, select: { _ in }, close: { _ in }, addTab: {}, changeMode: { privateMode = $0 }, closePrivate: {})
        overview.loadViewIfNeeded()
        let header = try XCTUnwrap(overview.tableView.tableHeaderView)
        let search = try XCTUnwrap(header.subviews.compactMap { $0 as? UISearchBar }.first)
        search.text = "Secret"
        overview.searchBar(search, textDidChange: "Secret")
        XCTAssertEqual(overview.tableView(overview.tableView, numberOfRowsInSection: 0), 0)
        let modes = try XCTUnwrap(header.subviews.compactMap { $0 as? UISegmentedControl }.first)
        modes.selectedSegmentIndex = 1
        modes.sendActions(for: .valueChanged)
        XCTAssertTrue(privateMode)
        XCTAssertEqual(search.text, "")
        XCTAssertEqual(overview.tableView(overview.tableView, numberOfRowsInSection: 0), 1)
        let cell = overview.tableView(overview.tableView, cellForRowAt: IndexPath(row: 0, section: 0))
        XCTAssertEqual(cell.textLabel?.text, "Secret document")
        XCTAssertFalse(cell.detailTextLabel?.text?.contains("regular.invalid") ?? true)
    }

    func testOverviewDisablesNewTabAtBoundAndUsesAccessibleCloseTargets() throws {
        var session = BrowserSession()
        while session.addTab() != nil {}
        let overview = BrowserTabsController(snapshot: {
            BrowserTabsSnapshot(tabs: session.tabs, selectedID: session.selectedID, isPrivate: false)
        }, select: { _ in }, close: { _ in }, addTab: {}, changeMode: { _ in }, closePrivate: {})
        overview.loadViewIfNeeded()
        XCTAssertFalse(try XCTUnwrap(overview.toolbarItems?.first).isEnabled)
        let row = overview.tableView(overview.tableView, cellForRowAt: IndexPath(row: 0, section: 0))
        let close = try XCTUnwrap(row.accessoryView as? UIButton)
        XCTAssertGreaterThanOrEqual(close.bounds.width, 44)
        XCTAssertGreaterThanOrEqual(close.bounds.height, 44)
        XCTAssertFalse(try XCTUnwrap(close.accessibilityLabel).isEmpty)
    }

    func testClosingSelectedFromOverviewDoesNotNavigateSavedReplacement() throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-tabs-" + UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = BrowserSessionStore(directory: directory)
        var session = BrowserSession()
        XCTAssertTrue(session.update(session.selectedID, url: "https://example.invalid/saved", title: "Saved"))
        let replacement = session.selectedID
        let selected = try XCTUnwrap(session.addTab())
        try store.save(session)
        let browser = BrowserController(sessionStore: store)
        browser.loadViewIfNeeded()
        let gate = XCTAttachment(string: "processWideClearPending=\(browser.isClearingSiteData)")
        gate.name = "tab-close-precondition.txt"
        gate.lifetime = .keepAlways
        add(gate)
        XCTAssertFalse(browser.isClearingSiteData, "A preceding site-data clear has not finished; tab mutation is intentionally blocked")
        guard !browser.isClearingSiteData else { return }
        browser.closeTab(selected, loadSavedPage: false)
        XCTAssertEqual(browser.sessionSnapshot.selectedID, replacement)
        func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }
        let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
        XCTAssertNil(page.url)
        XCTAssertFalse(page.isLoading)
    }

    func testPrivateOverviewCoversNavigationAndSearchWhileInactive() throws {
        let tab = BrowserTab(url: "https://private.invalid", title: "Secret")
        let overview = BrowserTabsController(snapshot: {
            BrowserTabsSnapshot(tabs: [tab], selectedID: tab.id, isPrivate: true)
        }, select: { _ in }, close: { _ in }, addTab: {}, changeMode: { _ in }, closePrivate: {})
        let navigation = UINavigationController(rootViewController: overview)
        navigation.loadViewIfNeeded()
        overview.loadViewIfNeeded()
        XCTAssertEqual(overview.navigationItem.leftBarButtonItem?.accessibilityIdentifier, "forge-tabs-close-private")
        XCTAssertEqual(overview.toolbarItems?.count, 1, "Long localized destructive labels must not overflow the bottom toolbar")
        navigation.view.frame = CGRect(x: 0, y: 0, width: 393, height: 852)
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        let cover = try XCTUnwrap(navigation.view.subviews.last)
        XCTAssertEqual(cover.accessibilityIdentifier, "forge-tabs-privacy-cover")
        XCTAssertEqual(cover.frame, navigation.view.bounds)
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        XCTAssertFalse(navigation.view.subviews.contains { $0.accessibilityIdentifier == "forge-tabs-privacy-cover" })
    }
}
