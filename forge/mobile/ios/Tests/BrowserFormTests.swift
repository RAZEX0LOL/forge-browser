import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserFormTests: XCTestCase {
    private let secret = "forge-sensitive-form-fixture"

    func testRequiredFieldsAndRegularPOSTKeepNativePolicyWithoutSavingValues() async throws {
        try await checkForm(privateMode: false, newWindow: false, expectedPolicy: .allow)
    }
    func testPrivatePOSTKeepsNativePolicyWithoutWritingRegularStorage() async throws {
        try await checkForm(privateMode: true, newWindow: false, expectedPolicy: .allow)
    }
    func testPrivatePOSTToNewWindowIsCancelledRatherThanReplayedAsGET() async throws {
        try await checkForm(privateMode: true, newWindow: true, expectedPolicy: .cancel)
    }

    private func checkForm(privateMode: Bool, newWindow: Bool, expectedPolicy: WKNavigationActionPolicy) async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-form-" + UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let sessions = BrowserSessionStore(directory: directory)
        try sessions.save(BrowserSession())
        let original = try Data(contentsOf: sessions.fileURL)
        let library = BrowserLibraryStore(directory: directory)
        let browser = BrowserController(sessionStore: sessions, libraryStore: library, dataStore: .nonPersistent())
        browser.loadViewIfNeeded()
        if privateMode { browser.setPrivateBrowsing(true) }
        func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }
        let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
        let loaded = expectation(description: "Local form source loaded")
        let submitted = expectation(description: "Native form POST policy observed")
        let observer = FormPolicyObserver(browser: browser, loaded: loaded, submitted: submitted)
        page.navigationDelegate = observer
        let target = newWindow ? "target='_blank'" : ""
        page.loadHTMLString("""
            <html><head><meta http-equiv='Content-Security-Policy'
              content="default-src 'none'; form-action https://form-fixture.invalid"></head><body>
            <form method='post' action='https://form-fixture.invalid/submit' \(target) autocomplete='off'>
              <input name='login' type='email' required autocomplete='off'>
              <input name='secret' type='password' required autocomplete='off'>
              <button type='submit'>Submit fixture</button>
            </form></body></html>
            """, baseURL: URL(string: "https://form-source-fixture.invalid/"))
        await fulfillment(of: [loaded], timeout: 60)
        let invalid = try await page.evaluateJavaScript("document.forms[0].checkValidity()")
        XCTAssertEqual(invalid as? Bool, false)
        let valid = try await page.evaluateJavaScript("""
            document.forms[0].elements.login.value = 'fixture@example.invalid';
            document.forms[0].elements.secret.value = '\(secret)';
            document.forms[0].requestSubmit();
            document.forms[0].checkValidity();
            """)
        XCTAssertEqual(valid as? Bool, true)
        await fulfillment(of: [submitted], timeout: 60)
        XCTAssertEqual(observer.method, "POST")
        XCTAssertEqual(observer.policy, expectedPolicy)
        XCTAssertEqual(observer.newWindow, newWindow)
        XCTAssertEqual(browser.sessionSnapshot.tabs.count, 1)
        XCTAssertNil(browser.presentedViewController)
        let saved = try Data(contentsOf: sessions.fileURL)
        XCTAssertFalse(String(decoding: saved, as: UTF8.self).contains(secret))
        XCTAssertFalse(String(decoding: try JSONEncoder().encode(library.snapshot), as: UTF8.self).contains(secret))
        if privateMode {
            XCTAssertEqual(saved, original)
            XCTAssertFalse(FileManager.default.fileExists(atPath: library.fileURL.path))
        }
        // The observer cancels the real destination after recording Forge's
        // decision, so no fixture credentials or POST body leave this process.
        withExtendedLifetime(observer) {}
    }
}

@MainActor
private final class FormPolicyObserver: NSObject, WKNavigationDelegate {
    private let browser: BrowserController
    private let loaded: XCTestExpectation
    private let submitted: XCTestExpectation
    private var didLoad = false
    private var didSubmit = false
    private(set) var method: String?
    private(set) var policy: WKNavigationActionPolicy?
    private(set) var newWindow: Bool?

    init(browser: BrowserController, loaded: XCTestExpectation, submitted: XCTestExpectation) {
        self.browser = browser; self.loaded = loaded; self.submitted = submitted
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if action.request.url?.host == "form-fixture.invalid" {
            browser.webView(webView, decidePolicyFor: action) { decision in
                self.method = action.request.httpMethod
                self.policy = decision
                self.newWindow = action.targetFrame == nil
                decisionHandler(.cancel)
                if !self.didSubmit { self.didSubmit = true; self.submitted.fulfill() }
            }
        } else { browser.webView(webView, decidePolicyFor: action, decisionHandler: decisionHandler) }
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        browser.webView(webView, didFinish: navigation)
        if !didLoad { didLoad = true; loaded.fulfill() }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if (error as NSError).code == NSURLErrorCancelled { return }
        XCTFail("Local form fixture failed: \((error as NSError).domain) \((error as NSError).code)")
        if !didLoad { didLoad = true; loaded.fulfill() }
    }
}
