import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserNewTabLinkTests: XCTestCase {
    private func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }
    private func page(_ browser: BrowserController) throws -> WKWebView {
        try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
    }
    private func fixture(tabs: Int = 1) throws -> (BrowserController, BrowserSessionStore, URL) {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-new-tab-" + UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let store = BrowserSessionStore(directory: directory)
        var session = BrowserSession()
        for _ in 1..<tabs { session.addTab() }
        try store.save(session)
        let browser = BrowserController(sessionStore: store, libraryStore: BrowserLibraryStore(directory: directory), dataStore: .nonPersistent())
        browser.loadViewIfNeeded()
        return (browser, store, directory)
    }
    private func attach(_ browser: BrowserController) throws -> () -> Void {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive })
        let window = try XCTUnwrap(scene.windows.first { $0.isKeyWindow && !$0.isHidden && $0.windowLevel == .normal })
        let previous = window.rootViewController
        window.rootViewController = browser; window.layoutIfNeeded()
        return { window.endEditing(true); window.rootViewController = previous }
    }
    private func load(_ browser: BrowserController, base: String = "https://source-fixture.invalid/") async throws -> WKWebView {
        let web = try page(browser)
        let done = expectation(description: "Local new-tab source loaded")
        let observer = NewTabDocumentObserver(browser: browser, done: done)
        web.navigationDelegate = observer
        web.loadHTMLString("<html><head><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'\"></head><body>Local link fixture</body></html>", baseURL: URL(string: base))
        await fulfillment(of: [done], timeout: 60)
        XCTAssertEqual(web.url?.absoluteString, base)
        web.navigationDelegate = browser
        withExtendedLifetime(observer) {}
        return web
    }

    func testNewTabConfirmationDefaultsToCancelWithoutMutation() throws {
        let (browser, _, _) = try fixture()
        let before = browser.sessionSnapshot
        let alert = browser.makeNewTabConfirmation(URL(string: "https://target-fixture.invalid/")!, from: try page(browser))
        XCTAssertEqual(alert.actions.map(\.style), [.cancel, .default])
        XCTAssertEqual(alert.preferredAction?.style, .cancel)
        XCTAssertEqual(browser.sessionSnapshot, before)
        XCTAssertNil(browser.presentedViewController)
    }

    func testDetachedAndUnsupportedSourcesCannotOpenTab() throws {
        let (browser, _, _) = try fixture()
        let source = try page(browser)
        XCTAssertFalse(browser.openLinkInNewTab(URL(string: "https://target-fixture.invalid/")!, from: source))
        XCTAssertFalse(browser.openLinkInNewTab(URL(string: "javascript:alert(1)")!, from: source))
        XCTAssertEqual(browser.sessionSnapshot.tabs.count, 1)
    }

    func testPrivateTabMutationsDoNotRewriteUnchangedRegularSnapshot() throws {
        let (browser, store, directory) = try fixture()
        let file = directory.appendingPathComponent("session-v1.json")
        let before = try Data(contentsOf: file)
        let attributes = try FileManager.default.attributesOfItem(atPath: file.path)
        browser.setPrivateBrowsing(true)
        XCTAssertTrue(browser.addTab())
        browser.closeTab(browser.sessionSnapshot.selectedID, loadSavedPage: false)
        XCTAssertEqual(try Data(contentsOf: file), before)
        let after = try FileManager.default.attributesOfItem(atPath: file.path)
        XCTAssertEqual(after[.systemFileNumber] as? NSNumber, attributes[.systemFileNumber] as? NSNumber)
        XCTAssertEqual(after[.modificationDate] as? Date, attributes[.modificationDate] as? Date)
        browser.setPrivateBrowsing(false)
        XCTAssertTrue(browser.addTab())
        XCTAssertEqual(try store.load(), browser.sessionSnapshot, "Changed regular tabs must still persist")
        XCTAssertEqual(browser.sessionSnapshot.tabs.count, 2)
    }

    func testConfirmedRegularLinkUsesSeparateWebViewAndPreservesOriginalTab() async throws {
        let (browser, _, _) = try fixture()
        let detach = try attach(browser); defer { detach() }
        let source = try await load(browser)
        let id = browser.sessionSnapshot.selectedID
        let target = URL(string: "https://target-fixture.invalid/")!
        XCTAssertTrue(browser.openLinkInNewTab(target, from: source))
        let destination = try page(browser)
        destination.stopLoading()
        XCTAssertFalse(destination === source)
        XCTAssertEqual(browser.sessionSnapshot.tabs.count, 2)
        XCTAssertEqual(browser.sessionSnapshot.selectedTab.url, target.absoluteString)
        XCTAssertNotEqual(browser.sessionSnapshot.selectedID, id)
        XCTAssertTrue(browser.sessionSnapshot.tabs.contains { $0.id == id && $0.url == "https://source-fixture.invalid/" })
        XCTAssertFalse(browser.isPrivateBrowsing)
        XCTAssertFalse(browser.openLinkInNewTab(target, from: source), "Old source must not create another tab")
    }

    func testConfirmedPrivateLinkStaysInGroupAndOffDisk() async throws {
        let (browser, _, directory) = try fixture()
        let detach = try attach(browser); defer { detach() }
        let file = directory.appendingPathComponent("session-v1.json")
        let before = try Data(contentsOf: file)
        browser.setPrivateBrowsing(true)
        let source = try await load(browser, base: "https://private-source-fixture.invalid/")
        XCTAssertTrue(browser.openLinkInNewTab(URL(string: "https://private-target-fixture.invalid/")!, from: source))
        let destination = try page(browser); destination.stopLoading()
        XCTAssertTrue(browser.isPrivateBrowsing)
        XCTAssertEqual(browser.sessionSnapshot.tabs.count, 2)
        XCTAssertTrue(destination.configuration.websiteDataStore === source.configuration.websiteDataStore)
        XCTAssertFalse(destination.configuration.websiteDataStore.isPersistent)
        XCTAssertEqual(try Data(contentsOf: file), before)
    }

    func testTabBoundPreventsOpeningWithoutChangingSelection() async throws {
        let (browser, _, _) = try fixture(tabs: BrowserSession.maximumTabs)
        let detach = try attach(browser); defer { detach() }
        let source = try await load(browser)
        let before = browser.sessionSnapshot
        XCTAssertFalse(browser.openLinkInNewTab(URL(string: "https://target-fixture.invalid/")!, from: source))
        XCTAssertEqual(browser.sessionSnapshot, before)
    }

    func testActivePageRejectsUnsupportedLinksAndModalPresentation() async throws {
        let (browser, _, _) = try fixture()
        let detach = try attach(browser); defer { detach() }
        let source = try await load(browser)
        let before = browser.sessionSnapshot
        for value in ["http://target-fixture.invalid/", "javascript:alert(1)", "https://user:secret@target-fixture.invalid/"] {
            XCTAssertFalse(browser.openLinkInNewTab(URL(string: value)!, from: source))
        }
        let modal = UIAlertController(title: "Fixture", message: nil, preferredStyle: .alert)
        browser.present(modal, animated: false)
        XCTAssertNotNil(browser.presentedViewController)
        XCTAssertFalse(browser.openLinkInNewTab(URL(string: "https://target-fixture.invalid/")!, from: source))
        XCTAssertEqual(browser.sessionSnapshot, before)
        modal.dismiss(animated: false)
    }
}

@MainActor
private final class NewTabDocumentObserver: NSObject, WKNavigationDelegate {
    private let browser: BrowserController
    private let done: XCTestExpectation
    init(browser: BrowserController, done: XCTestExpectation) { self.browser = browser; self.done = done }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        browser.webView(webView, decidePolicyFor: action, decisionHandler: decisionHandler)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        browser.webView(webView, didFinish: navigation); done.fulfill()
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        XCTFail("Local source failed: \((error as NSError).domain) \((error as NSError).code)"); done.fulfill()
    }
}
