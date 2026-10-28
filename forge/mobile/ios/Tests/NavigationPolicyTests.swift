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
        XCTAssertNil(web.url, "No startup network request")
        XCTAssertEqual(views.compactMap { $0 as? UIButton }.count, 4)
        field.text = "javascript:alert(1)"
        XCTAssertTrue(controller.textFieldShouldReturn(field))
        XCTAssertNil(web.url)
        XCTAssertTrue(status.text?.contains("Unsupported") == true)
    }
}
