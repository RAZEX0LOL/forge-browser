import XCTest
import UIKit
import AVFoundation
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserMediaPermissionTests: XCTestCase {
    private func host() throws -> (UIWindow, UIViewController, UIWindow?) {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previous = scene.windows.first { $0.isKeyWindow }
        let window = UIWindow(windowScene: scene)
        let presenter = UIViewController()
        window.rootViewController = presenter
        window.makeKeyAndVisible()
        presenter.loadViewIfNeeded()
        return (window, presenter, previous)
    }

    func testOriginDisplaysNoPathCredentialsOrQuerySecrets() {
        XCTAssertEqual(BrowserPermissionPolicy.origin("https://EXAMPLE.com:443/path?secret=1"), "https://example.com")
        XCTAssertEqual(BrowserPermissionPolicy.origin("https://example.com:8443/path"), "https://example.com:8443")
        XCTAssertEqual(BrowserPermissionPolicy.origin("https://[::1]:443/path"), "https://[::1]")
        for raw in ["http://example.com", "https://user:pass@example.com", "about:blank", "data:text/html,test",
                    "https://example.com:0", "https://example.com:65536", "https://example.com\n.evil"] { XCTAssertNil(BrowserPermissionPolicy.origin(raw), raw) }
    }

    func testMediaRequiresExplicitConsentBeforeSystemAuthorization() throws {
        let (window, presenter, previous) = try host()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        var authorizations: [AVMediaType] = []
        var decisions: [Bool] = []
        let permissions = BrowserMediaPermissions(authorize: { type, done in authorizations.append(type); done(true) }, foreground: { true })
        permissions.request(site: "https://example.com/path?secret=1", camera: true, microphone: false,
                            presenter: presenter, valid: { true }) { decisions.append($0) }
        let alert = try XCTUnwrap(permissions.pendingAlert)
        XCTAssertTrue(alert.preferredAction === alert.actions.first)
        XCTAssertFalse(alert.message?.contains("secret=1") ?? true)
        XCTAssertTrue(alert.message?.contains("https://example.com") ?? false)
        XCTAssertTrue(authorizations.isEmpty)
        XCTAssertTrue(decisions.isEmpty)
        permissions.allowPendingRequest()
        XCTAssertEqual(authorizations, [.video])
        XCTAssertEqual(decisions, [true])
        permissions.cancel()
        XCTAssertEqual(decisions, [true])
    }

    func testCancelledRequestCannotGrantFromLateSystemCallback() throws {
        let (window, presenter, previous) = try host()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        var systemCompletion: ((Bool) -> Void)?
        var decisions: [Bool] = []
        let permissions = BrowserMediaPermissions(authorize: { _, done in systemCompletion = done }, foreground: { true })
        permissions.request(site: "https://example.com", camera: true, microphone: false,
                            presenter: presenter, valid: { true }) { decisions.append($0) }
        permissions.allowPendingRequest()
        permissions.cancel()
        try XCTUnwrap(systemCompletion)(true)
        permissions.resume()
        XCTAssertEqual(decisions, [false])
    }

    func testSystemDenialNeverGrantsWebsiteAccess() throws {
        let (window, presenter, previous) = try host()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        var decisions: [Bool] = []
        let permissions = BrowserMediaPermissions(authorize: { _, done in done(false) }, foreground: { true })
        permissions.request(site: "https://example.com", camera: false, microphone: true,
                            presenter: presenter, valid: { true }) { decisions.append($0) }
        permissions.allowPendingRequest()
        XCTAssertEqual(decisions, [false])
    }

    func testBothSystemGrantsAndForegroundReturnAreRequiredWithoutSkippingSteps() throws {
        let (window, presenter, previous) = try host()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        var active = true
        var requested: [AVMediaType] = []
        var callbacks: [(Bool) -> Void] = []
        var decisions: [Bool] = []
        let permissions = BrowserMediaPermissions(authorize: { type, done in requested.append(type); callbacks.append(done) }, foreground: { active })
        permissions.request(site: "https://example.com", camera: true, microphone: true,
                            presenter: presenter, valid: { true }) { decisions.append($0) }
        permissions.allowPendingRequest()
        permissions.allowPendingRequest()
        XCTAssertEqual(requested, [.video])
        active = false
        permissions.resignActive()
        callbacks[0](true)
        XCTAssertTrue(decisions.isEmpty)
        active = true
        permissions.resume()
        XCTAssertEqual(requested, [.video, .audio])
        callbacks[1](true)
        XCTAssertEqual(decisions, [true])
    }

    func testChangedDocumentRejectsSystemApprovalAndConcurrentRequestsFailClosed() throws {
        let (window, presenter, previous) = try host()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        var valid = true
        var callback: ((Bool) -> Void)?
        var decisions: [Bool] = []
        let permissions = BrowserMediaPermissions(authorize: { _, done in callback = done }, foreground: { true })
        permissions.request(site: "https://example.com", camera: true, microphone: false,
                            presenter: presenter, valid: { valid }) { decisions.append($0) }
        permissions.request(site: "https://other.invalid", camera: true, microphone: false,
                            presenter: presenter, valid: { true }) { decisions.append($0) }
        permissions.allowPendingRequest()
        valid = false
        try XCTUnwrap(callback)(true)
        XCTAssertEqual(decisions, [false, false])
    }

    func testBackgroundAndInsecureRequestsNeverPresentOrAskSystem() throws {
        let (window, presenter, previous) = try host()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        var requests = 0
        var decisions: [Bool] = []
        let permissions = BrowserMediaPermissions(authorize: { _, _ in requests += 1 }, foreground: { false })
        permissions.request(site: "https://example.com", camera: true, microphone: false,
                            presenter: presenter, valid: { true }) { decisions.append($0) }
        let foreground = BrowserMediaPermissions(authorize: { _, _ in requests += 1 }, foreground: { true })
        foreground.request(site: "http://example.com", camera: true, microphone: false,
                           presenter: presenter, valid: { true }) { decisions.append($0) }
        XCTAssertEqual(requests, 0)
        XCTAssertEqual(decisions, [false, false])
        XCTAssertNil(presenter.presentedViewController)
    }
}
