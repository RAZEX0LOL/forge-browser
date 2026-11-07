import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserNavigationTests: XCTestCase {
    private func controller() -> BrowserController {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-navigation-" + UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let controller = BrowserController(sessionStore: BrowserSessionStore(directory: directory))
        controller.loadViewIfNeeded()
        return controller
    }

    private func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }

    func testErrorClassificationNeverReturnsRawSensitiveDescriptions() {
        let secret = [NSLocalizedDescriptionKey: "https://user:password@sensitive.invalid/?token=secret"]
        XCTAssertEqual(BrowserNavigationError.message(for: NSError(domain: NSURLErrorDomain,
            code: NSURLErrorTimedOut, userInfo: secret)), "Connection timed out. Try again.")
        for code in [NSURLErrorNotConnectedToInternet, NSURLErrorCannotFindHost, NSURLErrorNetworkConnectionLost] {
            XCTAssertEqual(BrowserNavigationError.message(for: NSError(domain: NSURLErrorDomain, code: code, userInfo: secret)),
                "Could not connect. Check your network and try again.")
        }
        XCTAssertEqual(BrowserNavigationError.message(for: NSError(domain: "Other", code: -1, userInfo: secret)),
            "Page could not be loaded.")
    }

    func testCertificateFailuresStayDistinctAndCancellationIsNotAnError() {
        for code in [NSURLErrorSecureConnectionFailed, NSURLErrorServerCertificateUntrusted,
                     NSURLErrorServerCertificateHasBadDate, NSURLErrorServerCertificateHasUnknownRoot] {
            XCTAssertEqual(BrowserNavigationError.message(for: NSError(domain: NSURLErrorDomain, code: code)),
                "Secure connection failed. No certificate exception was added.")
        }
        XCTAssertNil(BrowserNavigationError.message(for: NSError(domain: NSURLErrorDomain, code: NSURLErrorCancelled)))
    }

    func testStopIsNotReplacedByCancelledNavigationError() throws {
        let browser = controller()
        let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
        let status = try XCTUnwrap(descendants(browser.view).first { $0.accessibilityIdentifier == "forge-status" } as? UILabel)
        browser.stopLoadingSelected()
        let stopped = status.text
        XCTAssertFalse(status.isHidden)
        browser.webView(page, didFailProvisionalNavigation: nil,
            withError: NSError(domain: NSURLErrorDomain, code: NSURLErrorCancelled))
        XCTAssertEqual(status.text, stopped)
        XCTAssertNil(page.url)
        XCTAssertFalse(page.isLoading)
    }

    func testEndingAddressEditDiscardsDraftWithoutUpdatingSession() throws {
        let browser = controller()
        let before = browser.sessionSnapshot
        let field = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? UITextField }.first)
        field.text = "https://draft.invalid/not-submitted"
        browser.textFieldDidBeginEditing(field)
        XCTAssertNotNil(descendants(browser.view).first { $0.accessibilityIdentifier == "forge-address-cancel" })
        browser.cancelAddressEditing()
        browser.textFieldDidEndEditing(field)
        XCTAssertEqual(browser.sessionSnapshot, before)
        XCTAssertEqual(field.text, "")
        XCTAssertNotNil(descendants(browser.view).first { $0.accessibilityIdentifier == "forge-go" })
    }

    func testSelectedPageFailureShowsLocalizedRetryMessage() throws {
        let browser = controller()
        let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
        let status = try XCTUnwrap(descendants(browser.view).first { $0.accessibilityIdentifier == "forge-status" } as? UILabel)
        browser.webView(page, didFailProvisionalNavigation: nil,
            withError: NSError(domain: NSURLErrorDomain, code: NSURLErrorTimedOut))
        XCTAssertFalse(status.isHidden)
        XCTAssertEqual(status.text, NSLocalizedString("Connection timed out. Try again.", comment: ""))
        XCTAssertNotNil(descendants(browser.view).first { $0.accessibilityIdentifier == "forge-reload" })
    }
}
