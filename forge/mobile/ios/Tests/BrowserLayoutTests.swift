import XCTest
import UIKit
import WebKit
@testable import ForgeMobile

@MainActor
final class BrowserLayoutTests: XCTestCase {
    private func controller() -> BrowserController {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-layout-" + UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        let controller = BrowserController(sessionStore: BrowserSessionStore(directory: directory))
        controller.loadViewIfNeeded()
        return controller
    }

    private func descendants(_ view: UIView) -> [UIView] { [view] + view.subviews.flatMap(descendants) }

    func testEmptyTabHasNativeDarkStartWithoutRemoteNavigation() throws {
        let browser = controller()
        let views = descendants(browser.view)
        let start = try XCTUnwrap(views.first { $0.accessibilityIdentifier == "forge-start" })
        let web = try XCTUnwrap(views.compactMap { $0 as? WKWebView }.first)
        let status = try XCTUnwrap(views.first { $0.accessibilityIdentifier == "forge-status" })
        let address = try XCTUnwrap(views.compactMap { $0 as? UITextField }.first)
        XCTAssertFalse(start.isHidden)
        XCTAssertTrue(web.isHidden)
        XCTAssertNil(web.url)
        XCTAssertFalse(web.isOpaque)
        XCTAssertTrue(status.isHidden)
        XCTAssertEqual(address.textColor, BrowserPalette.foreground)
        XCTAssertNotNil(address.attributedPlaceholder?.attribute(.foregroundColor, at: 0, effectiveRange: nil))
    }

    func testBottomChromeFitsCompactPortraitLandscapeAndTabletWidths() throws {
        let browser = controller()
        for size in [CGSize(width: 320, height: 568), CGSize(width: 375, height: 667),
                     CGSize(width: 393, height: 852), CGSize(width: 852, height: 393), CGSize(width: 768, height: 1024)] {
            browser.view.frame = CGRect(origin: .zero, size: size)
            for _ in 0..<2 {
                browser.view.setNeedsLayout()
                browser.view.layoutIfNeeded()
            }
            let screenshot = UIGraphicsImageRenderer(size: size).image { _ in browser.view.drawHierarchy(in: browser.view.bounds, afterScreenUpdates: true) }
            let attachment = XCTAttachment(image: screenshot)
            attachment.name = "forge-home-\(Int(size.width))x\(Int(size.height))"
            attachment.lifetime = .keepAlways
            add(attachment)
            let views = descendants(browser.view)
            let field = try XCTUnwrap(views.compactMap { $0 as? UITextField }.first)
            let dock = try XCTUnwrap(views.first { $0.accessibilityIdentifier == "forge-browser-dock" })
            let bar = try XCTUnwrap(views.first { $0.accessibilityIdentifier == "forge-address-bar" })
            XCTAssertGreaterThan(field.bounds.width, 140, "Address field must not surrender space to the Go button")
            XCTAssertGreaterThan(dock.frame.minY, size.height * 0.5)
            XCTAssertLessThanOrEqual(dock.frame.maxY, size.height + 1)
            XCTAssertEqual(dock.frame.maxY, browser.view.safeAreaLayoutGuide.layoutFrame.maxY, accuracy: 1,
                           "A hidden keyboard must not leave a floating dock or dead space below it")
            XCTAssertGreaterThanOrEqual(bar.bounds.height, 56)
            let search = try XCTUnwrap(views.first { $0.accessibilityIdentifier == "forge-start-search" })
            XCTAssertLessThanOrEqual(search.convert(search.bounds, to: browser.view).maxY, dock.frame.minY + 1,
                                     "Start-page actions must fit above the dock, not be clipped behind it")
            for button in views.compactMap({ $0 as? UIButton }) where ["forge-go", "forge-back", "forge-forward", "forge-reload", "forge-tabs", "forge-new-tab"].contains(button.accessibilityIdentifier ?? "") {
                XCTAssertGreaterThanOrEqual(button.bounds.width, 44)
                XCTAssertGreaterThanOrEqual(button.bounds.height, 44)
            }
        }
    }

    func testBlockedInputKeepsNativeStartAndShowsReadableError() throws {
        let browser = controller()
        browser.view.frame = CGRect(x: 0, y: 0, width: 375, height: 667)
        let views = descendants(browser.view)
        let field = try XCTUnwrap(views.compactMap { $0 as? UITextField }.first)
        field.text = "javascript:alert(1)"
        XCTAssertTrue(browser.textFieldShouldReturn(field))
        browser.view.layoutIfNeeded()
        XCTAssertFalse(try XCTUnwrap(views.first { $0.accessibilityIdentifier == "forge-start" }).isHidden)
        XCTAssertFalse(try XCTUnwrap(views.first { $0.accessibilityIdentifier == "forge-status" }).isHidden)
        XCTAssertNil(views.compactMap { $0 as? WKWebView }.first?.url)
    }

    func testKeyboardKeepsAddressBarAboveSoftwareKeyboard() async throws {
        let browser = controller()
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive })
        let window = try XCTUnwrap(scene.windows.first { $0.isKeyWindow && !$0.isHidden && $0.windowLevel == .normal })
        let previousRoot = window.rootViewController
        window.rootViewController = browser
        window.layoutIfNeeded()
        defer { window.endEditing(true); window.rootViewController = previousRoot }
        let field = try XCTUnwrap(descendants(browser.view).compactMap { $0 as? UITextField }.first)
        let trace = KeyboardFocusTrace(field: field, window: window)
        trace.start()
        defer {
            trace.record("test.finished")
            let attachment = XCTAttachment(string: trace.json())
            attachment.name = "keyboard-focus-trace.json"
            attachment.lifetime = .keepAlways
            add(attachment)
            trace.stop()
        }
        let shown = expectation(description: "Software keyboard shown")
        var keyboardFrame: CGRect?
        let observer = OneShotKeyboardNotification(name: UIResponder.keyboardDidShowNotification) { notification in
            field.isFirstResponder && window.isKeyWindow &&
                notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] is CGRect
        } receive: { notification in
                keyboardFrame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect
                shown.fulfill()
            }
        defer { observer.cancel() }
        XCTAssertTrue(field.becomeFirstResponder())
        trace.record("test.requestedFocus")
        await fulfillment(of: [shown], timeout: 30)
        observer.cancel()
        trace.record("test.keyboardExpectationReturned")
        browser.view.layoutIfNeeded()
        trace.record("test.layoutCompleted")
        let frame = try XCTUnwrap(keyboardFrame)
        let addressFrame = field.convert(field.bounds, to: window)
        XCTAssertLessThanOrEqual(addressFrame.maxY, window.convert(frame, from: nil).minY)
        XCTAssertTrue(field.isFirstResponder)
        XCTAssertTrue(window.isKeyWindow)
        if field.isFirstResponder {
            let hidden = expectation(description: "Software keyboard hidden before restoring the host")
            let hideObserver = OneShotKeyboardNotification(name: UIResponder.keyboardDidHideNotification) { _ in
                !field.isFirstResponder && window.isKeyWindow
            } receive: { _ in hidden.fulfill() }
            defer { hideObserver.cancel() }
            field.resignFirstResponder()
            await fulfillment(of: [hidden], timeout: 30)
            trace.record("test.intentionalKeyboardCleanupCompleted")
        }
    }

    func testKeyboardNotificationConsumesOnlyFirstMatchingEventIncludingReentrantPosts() {
        let center = NotificationCenter()
        let name = Notification.Name("forge-test-keyboard")
        let once = expectation(description: "Only the first matching keyboard event")
        once.assertForOverFulfill = true
        var received = 0
        let observer = OneShotKeyboardNotification(center: center, name: name) {
            $0.userInfo?["matches"] as? Bool == true
        } receive: { _ in
            received += 1
            once.fulfill()
            center.post(name: name, object: nil, userInfo: ["matches": true])
        }
        defer { observer.cancel() }
        center.post(name: name, object: nil, userInfo: ["matches": false])
        XCTAssertEqual(received, 0)
        center.post(name: name, object: nil, userInfo: ["matches": true])
        center.post(name: name, object: nil, userInfo: ["matches": true])
        XCTAssertEqual(received, 1)
        wait(for: [once], timeout: 1)
    }

    func testCancelledKeyboardNotificationCannotCompleteLaterExpectation() {
        let center = NotificationCenter()
        let name = Notification.Name("forge-test-keyboard-cancelled")
        var received = 0
        let observer = OneShotKeyboardNotification(center: center, name: name, matches: { _ in true }) { _ in received += 1 }
        observer.cancel()
        observer.cancel()
        center.post(name: name, object: nil)
        XCTAssertEqual(received, 0)
    }
}

// Keyboard visibility notifications are a stream, not one event per focus request.
// Remove ownership before invoking the callback, including for reentrant posts.
@MainActor
private final class OneShotKeyboardNotification {
    private let center: NotificationCenter
    private var token: NSObjectProtocol?

    init(center: NotificationCenter = .default, name: Notification.Name,
         matches: @escaping (Notification) -> Bool, receive: @escaping (Notification) -> Void) {
        self.center = center
        token = center.addObserver(forName: name, object: nil, queue: .main) { [weak self] notification in
            MainActor.assumeIsolated {
                guard let self = self, self.token != nil, matches(notification) else { return }
                self.cancel()
                receive(notification)
            }
        }
    }

    func cancel() {
        if let token = token { center.removeObserver(token) }
        token = nil
    }
}

@MainActor
private final class KeyboardFocusTrace: NSObject, UITextFieldDelegate {
    private weak var field: UITextField?
    private weak var window: UIWindow?
    private weak var downstream: UITextFieldDelegate?
    private var observers: [NSObjectProtocol] = []
    private var events: [[String: Any]] = []
    private let started = ProcessInfo.processInfo.systemUptime

    init(field: UITextField, window: UIWindow) {
        self.field = field
        self.window = window
        downstream = field.delegate
    }

    func start() {
        field?.delegate = self
        let names: [Notification.Name] = [UIWindow.didBecomeKeyNotification, UIWindow.didResignKeyNotification,
            UIApplication.didBecomeActiveNotification, UIApplication.willResignActiveNotification,
            UIScene.didActivateNotification, UIScene.willDeactivateNotification,
            UITextField.textDidBeginEditingNotification, UITextField.textDidEndEditingNotification,
            UIResponder.keyboardWillChangeFrameNotification, UIResponder.keyboardDidShowNotification,
            UIResponder.keyboardWillHideNotification, UIResponder.keyboardDidHideNotification]
        for name in names {
            observers.append(NotificationCenter.default.addObserver(forName: name, object: nil, queue: .main) { [weak self] notification in
                MainActor.assumeIsolated { self?.record(notification.name.rawValue) }
            })
        }
        record("test.traceStarted")
    }

    func stop() {
        for observer in observers { NotificationCenter.default.removeObserver(observer) }
        observers.removeAll()
        field?.delegate = downstream
    }

    func record(_ event: String, stack: Bool = false) {
        guard let field = field, let window = window else { return }
        let windows = window.windowScene?.windows ?? []
        func responders(_ view: UIView) -> [String] {
            (view.isFirstResponder ? [String(describing: type(of: view))] : []) + view.subviews.flatMap(responders)
        }
        var row: [String: Any] = ["event": event, "seconds": ProcessInfo.processInfo.systemUptime - started,
            "fieldFirstResponder": field.isFirstResponder, "testWindowKey": window.isKeyWindow,
            "sceneState": window.windowScene?.activationState.rawValue ?? -100,
            "applicationState": UIApplication.shared.applicationState.rawValue,
            "firstResponderClasses": windows.flatMap(responders),
            "keyWindowRootClasses": windows.filter(\.isKeyWindow).map { window in
                window.rootViewController.map { String(describing: type(of: $0)) } ?? "nil"
            }]
        if stack { row["stack"] = Thread.callStackSymbols }
        events.append(row)
    }

    func json() -> String {
        let data = try! JSONSerialization.data(withJSONObject: events, options: [.prettyPrinted, .sortedKeys])
        return String(decoding: data, as: UTF8.self)
    }

    func textFieldDidBeginEditing(_ textField: UITextField) {
        record("delegate.didBegin.before")
        downstream?.textFieldDidBeginEditing?(textField)
        record("delegate.didBegin.after")
    }

    func textFieldDidEndEditing(_ textField: UITextField) {
        record("delegate.didEnd.before", stack: true)
        downstream?.textFieldDidEndEditing?(textField)
        record("delegate.didEnd.after")
    }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool { downstream?.textFieldShouldReturn?(textField) ?? true }
}
