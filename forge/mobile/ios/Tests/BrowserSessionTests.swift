import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

final class BrowserSessionTests: XCTestCase {
    private func store() throws -> BrowserSessionStore {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-session-test-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return BrowserSessionStore(directory: directory)
    }

    func testAtomicPersistenceAndSelectedTab() throws {
        let storage = try store()
        XCTAssertNil(try storage.load())
        var session = BrowserSession()
        let first = session.selectedID
        session.update(first, url: "https://example.com/path?q=hello#part", title: "Первый сайт")
        let second = session.addTab()!
        session.select(first)
        try storage.save(session)
        XCTAssertEqual(try storage.load(), session)
        session.close(second)
        session.close(first)
        XCTAssertEqual(session.tabs.count, 1)
        XCTAssertEqual(session.selectedTab.url, "about:blank")
        try storage.save(session)
        XCTAssertEqual(try storage.load(), session)
        let values = try storage.fileURL.deletingLastPathComponent().resourceValues(forKeys: [.isExcludedFromBackupKey])
        XCTAssertEqual(values.isExcludedFromBackup, true)
    }

    func testBoundedTabsAndInvalidUpdates() throws {
        var session = BrowserSession()
        for _ in 1..<BrowserSession.maximumTabs { XCTAssertNotNil(session.addTab()) }
        let before = session
        XCTAssertNil(session.addTab())
        XCTAssertFalse(session.select(UUID()))
        XCTAssertFalse(session.update(session.selectedID, url: "javascript:alert(1)", title: "bad"))
        XCTAssertEqual(session, before)
    }

    func testCorruptFutureDuplicateAndHostileSessionsStayUntouched() throws {
        let storage = try store()
        let valid = try JSONSerialization.jsonObject(with: JSONEncoder().encode(BrowserSession())) as! [String: Any]
        var fixtures = [Data("not json".utf8)]
        for version in [2, 0] {
            var data = valid; data["schemaVersion"] = version
            fixtures.append(try JSONSerialization.data(withJSONObject: data))
        }
        for url in ["javascript:alert(1)", "http://example.com", "file:///private", "https://user:pass@example.com"] {
            var data = valid
            var tabs = data["tabs"] as! [[String: Any]]
            tabs[0]["url"] = url; data["tabs"] = tabs
            fixtures.append(try JSONSerialization.data(withJSONObject: data))
        }
        var duplicate = valid
        duplicate["tabs"] = (valid["tabs"] as! [[String: Any]]) + (valid["tabs"] as! [[String: Any]])
        fixtures.append(try JSONSerialization.data(withJSONObject: duplicate))
        fixtures.append(Data(repeating: 32, count: BrowserSessionStore.maximumBytes + 1))
        for data in fixtures {
            try data.write(to: storage.fileURL)
            XCTAssertThrowsError(try storage.load())
            XCTAssertEqual(try Data(contentsOf: storage.fileURL), data)
        }
    }

    @MainActor
    func testNativeTabsStayIndependentAndColdRestoreDoesNotNavigate() throws {
        let storage = try store()
        let controller = BrowserController(sessionStore: storage)
        controller.loadViewIfNeeded()
        let first = controller.sessionSnapshot.selectedID
        let firstPage = controller.view.subviews.flatMap { descendants($0) }.compactMap { $0 as? WKWebView }.first!
        XCTAssertTrue(controller.addTab())
        let second = controller.sessionSnapshot.selectedID
        let secondPage = descendants(controller.view).compactMap { $0 as? WKWebView }.first!
        XCTAssertFalse(firstPage === secondPage)
        controller.selectTab(first)
        XCTAssertTrue(descendants(controller.view).compactMap { $0 as? WKWebView }.first! === firstPage)
        controller.closeTab(second)
        XCTAssertEqual(controller.sessionSnapshot.tabs.count, 1)
        var saved = controller.sessionSnapshot
        saved.update(first, url: "https://example.com/")
        try storage.save(saved)
        let restored = BrowserController(sessionStore: storage)
        restored.loadViewIfNeeded()
        XCTAssertEqual(restored.sessionSnapshot, saved)
        XCTAssertNil(descendants(restored.view).compactMap { $0 as? WKWebView }.first!.url)
        XCTAssertTrue(descendants(restored.view).compactMap { $0 as? WKWebView }.first!.isHidden)
        XCTAssertFalse(descendants(restored.view).first { $0.accessibilityIdentifier == "forge-start" }!.isHidden)
    }

    @MainActor
    private func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }

    @MainActor
    func testPrivateTabsNeverPersistAndUseSharedEphemeralStore() throws {
        let storage = try store()
        let controller = BrowserController(sessionStore: storage)
        controller.loadViewIfNeeded()
        XCTAssertTrue(controller.addTab())
        let regular = controller.sessionSnapshot
        controller.setPrivateBrowsing(true)
        let first = try XCTUnwrap(descendants(controller.view).compactMap { $0 as? WKWebView }.first)
        XCTAssertFalse(first.configuration.websiteDataStore.isPersistent)
        let privateID = controller.sessionSnapshot.selectedID
        let address = try XCTUnwrap(descendants(controller.view).compactMap { $0 as? UITextField }.first)
        address.text = "https://forge-private.invalid/private-secret"
        XCTAssertTrue(controller.textFieldShouldReturn(address))
        XCTAssertEqual(controller.sessionSnapshot.selectedTab.url, "https://forge-private.invalid/private-secret")
        XCTAssertTrue(controller.addTab())
        let second = try XCTUnwrap(descendants(controller.view).compactMap { $0 as? WKWebView }.first)
        XCTAssertTrue(first.configuration.websiteDataStore === second.configuration.websiteDataStore)
        NotificationCenter.default.post(name: UIApplication.didEnterBackgroundNotification, object: nil)
        XCTAssertEqual(try storage.load(), regular)
        XCTAssertFalse(try String(contentsOf: storage.fileURL, encoding: .utf8).contains("private-secret"))
        NotificationCenter.default.post(name: UIApplication.willResignActiveNotification, object: nil)
        XCTAssertNotNil(descendants(controller.view).first { $0.accessibilityIdentifier == "forge-privacy-cover" })
        NotificationCenter.default.post(name: UIApplication.didBecomeActiveNotification, object: nil)
        XCTAssertNil(descendants(controller.view).first { $0.accessibilityIdentifier == "forge-privacy-cover" })
        let cold = BrowserController(sessionStore: storage)
        cold.loadViewIfNeeded()
        XCTAssertFalse(cold.isPrivateBrowsing)
        XCTAssertEqual(cold.sessionSnapshot, regular)
        controller.setPrivateBrowsing(false)
        XCTAssertEqual(controller.sessionSnapshot, regular)
        controller.setPrivateBrowsing(true)
        XCTAssertEqual(controller.sessionSnapshot.tabs.count, 2)
        controller.closePrivateTabs()
        XCTAssertFalse(controller.isPrivateBrowsing)
        controller.setPrivateBrowsing(true)
        XCTAssertEqual(controller.sessionSnapshot.tabs.count, 1)
        XCTAssertNotEqual(controller.sessionSnapshot.selectedID, privateID)
        let fresh = try XCTUnwrap(descendants(controller.view).compactMap { $0 as? WKWebView }.first)
        XCTAssertFalse(fresh.configuration.websiteDataStore === first.configuration.websiteDataStore)
    }

    @MainActor
    func testPrivateCookiesAreNotVisibleToRegularOrNewPrivateGroup() async throws {
        let controller = BrowserController(sessionStore: try store())
        controller.loadViewIfNeeded()
        let regular = try XCTUnwrap(descendants(controller.view).compactMap { $0 as? WKWebView }.first)
        controller.setPrivateBrowsing(true)
        let page = try XCTUnwrap(descendants(controller.view).compactMap { $0 as? WKWebView }.first)
        let cookie = try XCTUnwrap(HTTPCookie(properties: [.domain: "forge-private.invalid", .path: "/", .name: UUID().uuidString,
                                                        .value: "private-secret", .secure: "TRUE"]))
        await page.configuration.websiteDataStore.httpCookieStore.setCookie(cookie)
        let privateCookies = await page.configuration.websiteDataStore.httpCookieStore.allCookies()
        XCTAssertTrue(privateCookies.contains { $0.name == cookie.name })
        let regularCookies = await regular.configuration.websiteDataStore.httpCookieStore.allCookies()
        XCTAssertFalse(regularCookies.contains { $0.name == cookie.name })
        controller.closePrivateTabs()
        controller.setPrivateBrowsing(true)
        let fresh = try XCTUnwrap(descendants(controller.view).compactMap { $0 as? WKWebView }.first)
        let freshCookies = await fresh.configuration.websiteDataStore.httpCookieStore.allCookies()
        XCTAssertFalse(freshCookies.contains { $0.name == cookie.name })
    }
}
