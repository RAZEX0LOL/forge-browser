import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

final class NavigationPolicyTests: XCTestCase {
    func testHTTPSAndSearch() {
        XCTAssertEqual(NavigationPolicy.input("example.com")?.absoluteString, "https://example.com")
        XCTAssertEqual(NavigationPolicy.input("https://example.com/path")?.host, "example.com")
        let search = URLComponents(url: NavigationPolicy.input("two words")!, resolvingAgainstBaseURL: false)
        XCTAssertEqual(search?.queryItems?.first?.value, "two words")
    }
    func testRejectLocalActiveCleartextAndCredentials() {
        for input in ["javascript:alert(1)", "file:///etc/passwd", "data:text/html,test", "http://example.com", "https://user:pass@example.com"] {
            XCTAssertNil(NavigationPolicy.input(input), input)
        }
    }

    @MainActor
    func testNativeBrowserControlsAndBlockedInput() {
        let controller = BrowserController()
        controller.loadViewIfNeeded()
        func descendants(_ view: UIView) -> [UIView] {
            [view] + view.subviews.flatMap { descendants($0) }
        }
        let views = descendants(controller.view)
        let field = views.compactMap { $0 as? UITextField }.first!
        let web = views.compactMap { $0 as? WKWebView }.first!
        let status = views.compactMap { $0 as? UILabel }.first { $0.accessibilityIdentifier == "forge-status" }!
        XCTAssertNotNil(web.navigationDelegate)
        XCTAssertTrue(web.configuration.websiteDataStore.isPersistent)
        XCTAssertNil(web.url, "No startup page navigation")
        XCTAssertEqual(views.compactMap { $0 as? UIButton }.count, 4)
        field.text = "javascript:alert(1)"
        XCTAssertTrue(controller.textFieldShouldReturn(field))
        XCTAssertNil(web.url)
        XCTAssertTrue(status.text?.contains("Unsupported") == true)
    }

    @MainActor
    func testWebKitRendersLocalDocumentThroughBrowserPolicy() async throws {
        let controller = BrowserController()
        controller.loadViewIfNeeded()
        func findWeb(_ view: UIView) -> WKWebView? {
            if let web = view as? WKWebView { return web }
            return view.subviews.compactMap { findWeb($0) }.first
        }
        let web = findWeb(controller.view)!
        let loaded = expectation(description: "Local document rendered")
        let observer = LocalLoadObserver(controller: controller, loaded: loaded)
        web.navigationDelegate = observer
        web.loadHTMLString("<html><body><h1 id='fixture'>Forge fixture</h1></body></html>", baseURL: nil)
        await fulfillment(of: [loaded], timeout: 15)
        let text = try await web.evaluateJavaScript("document.getElementById('fixture').textContent")
        XCTAssertEqual(text as? String, "Forge fixture")
        withExtendedLifetime(observer) {}
    }
}

@MainActor
private final class LocalLoadObserver: NSObject, WKNavigationDelegate {
    let controller: BrowserController
    let loaded: XCTestExpectation
    init(controller: BrowserController, loaded: XCTestExpectation) {
        self.controller = controller
        self.loaded = loaded
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        controller.webView(webView, decidePolicyFor: action, decisionHandler: decisionHandler)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        controller.webView(webView, didFinish: navigation)
        loaded.fulfill()
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        XCTFail("Local document load failed: \(error)")
        loaded.fulfill()
    }
}
