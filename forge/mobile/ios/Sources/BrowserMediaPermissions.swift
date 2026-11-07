/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import UIKit
import AVFoundation
import WebKit

@MainActor
final class BrowserDeniedPermissions: NSObject, WKUIDelegate {
    static let shared = BrowserDeniedPermissions()
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) { decisionHandler(.deny) }
    func webView(_ webView: WKWebView, requestDeviceOrientationAndMotionPermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, decisionHandler: @escaping (WKPermissionDecision) -> Void) { decisionHandler(.deny) }
    @available(iOS 27.0, *)
    func webView(_ webView: WKWebView, requestGeolocationPermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, decisionHandler: @escaping (WKPermissionDecision) -> Void) { decisionHandler(.deny) }
}

enum BrowserPermissionPolicy {
    static func origin(_ raw: String?) -> String? {
        guard let raw = raw, raw.unicodeScalars.allSatisfy({ $0.value > 32 && $0.value != 127 }),
              let url = URL(string: raw), let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              components.scheme?.lowercased() == "https", components.user == nil, components.password == nil,
              var host = url.host?.lowercased(), !host.isEmpty, !host.contains("%"),
              host.unicodeScalars.allSatisfy({ $0.isASCII && $0.value > 32 }),
              components.port == nil || (1...65535).contains(components.port!) else { return nil }
        if host.contains(":"), !host.hasPrefix("[") { host = "[" + host + "]" }
        let port = components.port ?? 443
        return "https://" + host + (port == 443 ? "" : ":\(port)")
    }
}

@MainActor
final class BrowserMediaPermissions {
    typealias Authorize = @MainActor (AVMediaType, @escaping (Bool) -> Void) -> Void
    private let authorize: Authorize
    private let foreground: @MainActor () -> Bool
    private var pending: Pending?
    deinit { pending?.completion(false) }

    private final class Pending {
        let valid: () -> Bool
        let completion: (Bool) -> Void
        var alert: UIAlertController?
        var media: [AVMediaType]
        var waitingSystem = false
        var systemResult: Bool?
        init(media: [AVMediaType], valid: @escaping () -> Bool, completion: @escaping (Bool) -> Void) {
            self.media = media; self.valid = valid; self.completion = completion
        }
    }

    init(authorize: @escaping Authorize = BrowserMediaPermissions.systemAuthorize,
         foreground: @escaping @MainActor () -> Bool = { UIApplication.shared.applicationState == .active }) {
        self.authorize = authorize
        self.foreground = foreground
    }

    private static func systemAuthorize(_ type: AVMediaType, completion: @escaping (Bool) -> Void) {
        switch AVCaptureDevice.authorizationStatus(for: type) {
        case .authorized: completion(true)
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: type) { allowed in DispatchQueue.main.async { completion(allowed) } }
        default: completion(false)
        }
    }

    var pendingAlert: UIAlertController? { pending?.alert }

    func request(site: String, camera: Bool, microphone: Bool, presenter: UIViewController,
                 valid: @escaping () -> Bool, completion: @escaping (Bool) -> Void) {
        guard let origin = BrowserPermissionPolicy.origin(site), (camera || microphone), pending == nil,
              foreground(), valid(), presenter.viewIfLoaded?.window?.isKeyWindow == true,
              presenter.presentedViewController == nil else { completion(false); return }
        let media: [AVMediaType] = (camera ? [.video] : []) + (microphone ? [.audio] : [])
        let request = Pending(media: media, valid: valid, completion: completion)
        pending = request
        let text: (String) -> String = { NSLocalizedString($0, comment: "Site permissions") }
        let kind = text(camera && microphone ? "Camera and microphone" : camera ? "Camera" : "Microphone")
        let alert = UIAlertController(title: text("Site access"),
            message: String(format: text("Site media access warning"), origin, kind), preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: text("Deny"), style: .cancel) { [weak self] _ in self?.finish(request, allowed: false) })
        alert.addAction(UIAlertAction(title: text("Allow"), style: .default) { [weak self] _ in self?.authorizeNext(request) })
        alert.preferredAction = alert.actions.first
        request.alert = alert
        presenter.present(alert, animated: true)
    }

    // The same transition is used by the native Allow action and focused tests.
    func allowPendingRequest() { if let request = pending { authorizeNext(request) } }

    private func authorizeNext(_ request: Pending) {
        guard pending === request else { return }
        guard !request.waitingSystem else { return }
        guard foreground(), request.valid() else { finish(request, allowed: false); return }
        guard !request.media.isEmpty else { finish(request, allowed: true); return }
        let type = request.media.removeFirst()
        request.waitingSystem = true
        request.systemResult = nil
        request.alert?.dismiss(animated: false)
        authorize(type) { [weak self] allowed in
            guard let self = self, self.pending === request else { return }
            request.systemResult = allowed
            self.resume()
        }
    }

    func resume() {
        guard let request = pending, let allowed = request.systemResult, foreground() else { return }
        request.systemResult = nil
        request.waitingSystem = false
        if allowed { authorizeNext(request) } else { finish(request, allowed: false) }
    }

    private func finish(_ request: Pending, allowed: Bool) {
        guard pending === request else { return }
        pending = nil
        request.alert?.dismiss(animated: false)
        request.completion(allowed && foreground() && request.valid())
    }

    func cancel() { if let request = pending { finish(request, allowed: false) } }
    func resignActive() { if pending?.waitingSystem != true { cancel() } }
}
