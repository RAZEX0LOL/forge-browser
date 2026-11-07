import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserLibraryIntegrationTests: XCTestCase {
    private func fixture() throws -> (BrowserLibraryStore, BrowserSessionStore) {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-library-ui-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return (BrowserLibraryStore(directory: directory), BrowserSessionStore(directory: directory))
    }
    private func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }

    func testExplicitBookmarkCanSaveRestoredURLWithoutLoadingAndPrivateModeCannotSave() throws {
        let (library, sessions) = try fixture()
        var session = BrowserSession()
        session.update(session.selectedID, url: "https://bookmark-fixture.invalid", title: "Saved fixture")
        try sessions.save(session)
        let browser = BrowserController(sessionStore: sessions, libraryStore: library, dataStore: .nonPersistent())
        browser.loadViewIfNeeded()
        XCTAssertTrue(browser.bookmarkSelected())
        XCTAssertEqual(library.snapshot.bookmarks.first?.url, session.selectedTab.url)
        let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
        XCTAssertNil(page.url)
        let before = try Data(contentsOf: library.fileURL)
        browser.setPrivateBrowsing(true)
        XCTAssertFalse(browser.bookmarkSelected())
        XCTAssertEqual(try Data(contentsOf: library.fileURL), before)
    }

    func testLibraryFilteringAndHistoryConfirmationDoNotNavigateOrDeleteOnPresentation() throws {
        let (store, _) = try fixture()
        try store.addBookmark(url: "https://bookmark-fixture.invalid", title: "Bookmark fixture", isPrivate: false)
        try store.recordVisit(url: "https://history-fixture.invalid", title: "History fixture", isPrivate: false)
        var opened = false
        let library = BrowserLibraryController(store: store, bookmarks: true, privateMode: false) { _ in opened = true }
        library.loadViewIfNeeded()
        XCTAssertEqual(library.tableView(library.tableView, numberOfRowsInSection: 0), 1)
        let header = try XCTUnwrap(library.tableView.tableHeaderView)
        let search = try XCTUnwrap(header.subviews.compactMap { $0 as? UISearchBar }.first)
        search.text = "HISTORY-FIXTURE"
        library.searchBar(search, textDidChange: "HISTORY-FIXTURE")
        XCTAssertEqual(library.tableView(library.tableView, numberOfRowsInSection: 0), 0)
        let modes = try XCTUnwrap(header.subviews.compactMap { $0 as? UISegmentedControl }.first)
        modes.selectedSegmentIndex = 1; modes.sendActions(for: .valueChanged)
        XCTAssertEqual(search.text, "")
        XCTAssertEqual(library.tableView(library.tableView, numberOfRowsInSection: 0), 1)
        let confirmation = library.makeClearHistoryConfirmation()
        XCTAssertEqual(confirmation.preferredAction?.style, .cancel)
        XCTAssertEqual(confirmation.actions.map(\.style), [.cancel, .destructive])
        XCTAssertEqual(store.snapshot.history.count, 1)
        XCTAssertEqual(store.snapshot.bookmarks.count, 1)
        XCTAssertFalse(opened)
    }

    func testPrivateLibraryIsCoveredWhileInactive() throws {
        let (store, _) = try fixture()
        let library = BrowserLibraryController(store: store, bookmarks: true, privateMode: true) { _ in }
        let navigation = UINavigationController(rootViewController: library)
        navigation.loadViewIfNeeded(); library.loadViewIfNeeded()
        navigation.view.frame = CGRect(x: 0, y: 0, width: 393, height: 852)
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        XCTAssertEqual(navigation.view.subviews.last?.accessibilityIdentifier, "forge-library-privacy-cover")
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        XCTAssertFalse(navigation.view.subviews.contains { $0.accessibilityIdentifier == "forge-library-privacy-cover" })
    }

    func testCompletedLocalHTTPSBaseDocumentRecordsOnlyRegularVisit() async throws {
        let (store, sessions) = try fixture()
        let browser = BrowserController(sessionStore: sessions, libraryStore: store, dataStore: .nonPersistent())
        browser.loadViewIfNeeded()
        func load(_ base: String) async throws {
            let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
            let done = expectation(description: "Local library document completed")
            let observer = LibraryDocumentObserver(browser: browser, done: done)
            page.navigationDelegate = observer
            page.loadHTMLString("<html><head><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'\"><title>Library fixture</title></head><body>Local library fixture</body></html>", baseURL: URL(string: base))
            await fulfillment(of: [done], timeout: 60)
            XCTAssertEqual(page.url?.absoluteString, base)
            withExtendedLifetime(observer) {}
        }
        try await load("https://library-regular.invalid/")
        XCTAssertEqual(store.snapshot.history.map(\.url), ["https://library-regular.invalid/"])
        let before = try Data(contentsOf: store.fileURL)
        browser.setPrivateBrowsing(true)
        try await load("https://library-private.invalid/")
        XCTAssertEqual(try Data(contentsOf: store.fileURL), before)
    }
}

@MainActor
private final class LibraryDocumentObserver: NSObject, WKNavigationDelegate {
    private let browser: BrowserController
    private let done: XCTestExpectation
    private var completed = false
    init(browser: BrowserController, done: XCTestExpectation) { self.browser = browser; self.done = done }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        browser.webView(webView, decidePolicyFor: action, decisionHandler: decisionHandler)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        browser.webView(webView, didFinish: navigation)
        finish()
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        XCTFail("Local library fixture failed: \((error as NSError).domain) \((error as NSError).code)"); finish()
    }
    private func finish() { guard !completed else { return }; completed = true; done.fulfill() }
}
