import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserSiteDataTests: XCTestCase {
    private func store() -> BrowserSessionStore {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-clear-" + UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return BrowserSessionStore(directory: directory)
    }

    private func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }

    private func page(_ controller: BrowserController) throws -> WKWebView {
        try XCTUnwrap(descendants(controller.view).compactMap { $0 as? WKWebView }.first)
    }

    func testConfirmationDefaultsToCancelAndDoesNotClearOrClosePages() throws {
        var calls = 0
        let controller = BrowserController(sessionStore: store(), dataStore: .nonPersistent(), siteDataClearer: { _, _ in calls += 1 })
        controller.loadViewIfNeeded()
        let original = try page(controller)
        let confirmation = controller.makeClearSiteDataConfirmation()
        XCTAssertEqual(confirmation.actions.map(\.style), [.cancel, .destructive])
        XCTAssertTrue(confirmation.preferredAction === confirmation.actions.first)
        XCTAssertNotNil(confirmation.message)
        XCTAssertEqual(calls, 0)
        XCTAssertFalse(controller.isClearingSiteData)
        XCTAssertTrue(try page(controller) === original)
    }

    func testNativeClearingRemovesCookiesFromRegularAndPrivateStoresWithoutNavigating() async throws {
        let started = ProcessInfo.processInfo.systemUptime
        var events: [[String: Any]] = []
        var completed = false
        func record(_ phase: String) {
            events.append(["phase": phase, "seconds": ProcessInfo.processInfo.systemUptime - started])
        }
        defer {
            record("test.finished")
            let data = try! JSONSerialization.data(withJSONObject: events, options: [.prettyPrinted, .sortedKeys])
            let attachment = XCTAttachment(data: data, uniformTypeIdentifier: "public.json")
            attachment.name = "native-site-data-clear-timing.json"
            attachment.lifetime = .keepAlways
            add(attachment)
        }
        let storage = store()
        let regularStore = WKWebsiteDataStore.nonPersistent()
        let controller = BrowserController(sessionStore: storage, dataStore: regularStore, siteDataClearer: { stores, done in
            events.append(["phase": "native.clear.started", "seconds": ProcessInfo.processInfo.systemUptime - started,
                "storeCount": stores.count, "persistentStoreCount": stores.filter(\.isPersistent).count])
            BrowserSiteData.clear(stores) { success in
                events.append(["phase": "native.clear.callback", "seconds": ProcessInfo.processInfo.systemUptime - started,
                    "success": success])
                done(success)
            }
        })
        controller.loadViewIfNeeded()
        XCTAssertFalse(controller.isClearingSiteData, "A previous process-wide clear is still pending; this fixture is not isolated")
        guard !controller.isClearingSiteData else { return }
        XCTAssertTrue(controller.addTab())
        let regular = controller.sessionSnapshot
        let oldRegular = try page(controller)
        controller.setPrivateBrowsing(true)
        let oldPrivate = try page(controller)
        let cookie = try XCTUnwrap(HTTPCookie(properties: [.domain: "forge-clear.invalid", .path: "/", .name: UUID().uuidString, .value: "fixture"]))
        await regularStore.httpCookieStore.setCookie(cookie)
        await oldPrivate.configuration.websiteDataStore.httpCookieStore.setCookie(cookie)
        record("test.cookiesSeeded")
        let done = expectation(description: "Native WebKit clearing")
        controller.clearSiteDataConfirmed { success in completed = true; XCTAssertTrue(success); done.fulfill() }
        await fulfillment(of: [done], timeout: 60)
        events.append(["phase": "test.expectationReturned", "seconds": ProcessInfo.processInfo.systemUptime - started,
            "completed": completed, "processWideClearPending": controller.isClearingSiteData])
        // The failed 60-second expectation remains a failure. Do not block the
        // runner indefinitely on more WebKit callbacks or reset the production gate.
        guard completed else { return }
        let regularCookies = await regularStore.httpCookieStore.allCookies()
        let privateCookies = await oldPrivate.configuration.websiteDataStore.httpCookieStore.allCookies()
        XCTAssertFalse(regularCookies.contains { $0.name == cookie.name })
        XCTAssertFalse(privateCookies.contains { $0.name == cookie.name })
        XCTAssertNil(oldRegular.navigationDelegate)
        XCTAssertNil(oldPrivate.navigationDelegate)
        XCTAssertTrue(oldRegular.uiDelegate === BrowserDeniedPermissions.shared)
        XCTAssertTrue(oldPrivate.uiDelegate === BrowserDeniedPermissions.shared)
        XCTAssertFalse(controller.isPrivateBrowsing)
        XCTAssertEqual(controller.sessionSnapshot, regular)
        XCTAssertEqual(try storage.load(), regular)
        let fresh = try page(controller)
        XCTAssertFalse(fresh === oldRegular)
        XCTAssertNil(fresh.url)
        XCTAssertTrue(controller.view.isUserInteractionEnabled)
    }

    func testClearingFreezesAllWindowsAndNewControllersThenReportsFailureAndAllowsRetry() throws {
        var finish: ((Bool) -> Void)?
        let controller = BrowserController(sessionStore: store(), dataStore: .nonPersistent(), siteDataClearer: { stores, completion in
            XCTAssertGreaterThanOrEqual(stores.count, 4)
            finish = completion
        })
        let other = BrowserController(sessionStore: store(), dataStore: .nonPersistent())
        controller.loadViewIfNeeded()
        other.loadViewIfNeeded()
        let otherPage = try page(other)
        controller.clearSiteDataConfirmed()
        XCTAssertTrue(controller.isClearingSiteData)
        XCTAssertTrue(other.isClearingSiteData)
        XCTAssertFalse(other.view.isUserInteractionEnabled)
        XCTAssertNil(otherPage.navigationDelegate)
        XCTAssertFalse(other.addTab())
        other.setPrivateBrowsing(true)
        XCTAssertFalse(other.isPrivateBrowsing)
        let newWindow = BrowserController(sessionStore: store(), dataStore: .nonPersistent())
        newWindow.loadViewIfNeeded()
        XCTAssertFalse(newWindow.view.isUserInteractionEnabled)
        XCTAssertTrue(descendants(newWindow.view).compactMap { $0 as? WKWebView }.isEmpty)
        try XCTUnwrap(finish)(false)
        for window in [controller, other, newWindow] {
            XCTAssertFalse(window.isClearingSiteData)
            XCTAssertTrue(window.view.isUserInteractionEnabled)
            XCTAssertNil(try page(window).url)
            let status = try XCTUnwrap(descendants(window.view).compactMap { $0 as? UILabel }.first { $0.accessibilityIdentifier == "forge-status" })
            XCTAssertEqual(status.text, NSLocalizedString("Site data could not be fully cleared. Try again.", comment: ""))
        }
        controller.clearSiteDataConfirmed()
        XCTAssertTrue(controller.isClearingSiteData)
        try XCTUnwrap(finish)(true)
        XCTAssertFalse(controller.isClearingSiteData)
    }

    func testClearingDoesNotOverwriteCorruptSession() throws {
        let storage = store()
        try FileManager.default.createDirectory(at: storage.fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        let corrupt = Data("corrupt fixture".utf8)
        try corrupt.write(to: storage.fileURL)
        let controller = BrowserController(sessionStore: storage, dataStore: .nonPersistent(), siteDataClearer: { _, done in done(true) })
        controller.loadViewIfNeeded()
        controller.clearSiteDataConfirmed()
        NotificationCenter.default.post(name: UIApplication.didEnterBackgroundNotification, object: nil)
        XCTAssertEqual(try Data(contentsOf: storage.fileURL), corrupt)
    }
}
