import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserLinkActionsTests: XCTestCase {
    func testOnlyBoundedCredentialFreeHTTPSLinksCanBeShared() {
        for value in ["about:blank", "http://example.invalid", "file:///private", "javascript:alert(1)",
                      "mailto:user@example.invalid", "https://user:secret@example.invalid",
                      "https://example.invalid/" + String(repeating: "a", count: 8192)] {
            XCTAssertNil(BrowserLinkActions.shareURL(value))
        }
        XCTAssertEqual(BrowserLinkActions.shareURL("https://example.invalid/page?q=value#part")?.absoluteString,
            "https://example.invalid/page?q=value#part")
    }

    private func controller(savedURL: String? = nil) throws -> BrowserController {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-link-" + UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let store = BrowserSessionStore(directory: directory)
        if let url = savedURL {
            var session = BrowserSession()
            XCTAssertTrue(session.update(session.selectedID, url: url))
            try store.save(session)
        }
        let browser = BrowserController(sessionStore: store)
        browser.loadViewIfNeeded()
        return browser
    }

    func testShareSheetIsUnavailableForBlankButCanBePreparedWithoutNavigatingSavedLink() throws {
        XCTAssertNil(try controller().makeShareController())
        let browser = try controller(savedURL: "https://example.invalid/shared")
        XCTAssertNotNil(browser.makeShareController())
        func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }
        let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
        XCTAssertNil(page.url)
        XCTAssertFalse(page.isLoading)
        XCTAssertNil(browser.presentedViewController)
    }

    func testPrivateShareConfirmationDefaultsToCancelAndDoesNotPresentRecipient() throws {
        let browser = try controller()
        browser.setPrivateBrowsing(true)
        let confirmation = browser.makePrivateShareConfirmation()
        XCTAssertEqual(confirmation.actions.count, 2)
        XCTAssertEqual(confirmation.preferredAction?.style, .cancel)
        XCTAssertNil(browser.presentedViewController)
        XCTAssertTrue(browser.isPrivateBrowsing)
    }

    func testPageUsesNativeWebKitFindInteractionRatherThanInjectedSearchScript() throws {
        let browser = try controller()
        func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }
        let page = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? WKWebView }.first)
        XCTAssertTrue(page.isFindInteractionEnabled)
        XCTAssertNotNil(page.findInteraction)
    }
}
