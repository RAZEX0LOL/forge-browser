import XCTest
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
}
