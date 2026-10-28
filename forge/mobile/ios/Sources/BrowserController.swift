/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import UIKit
import WebKit

final class BrowserController: UIViewController, WKNavigationDelegate, UITextFieldDelegate {
    private let address = UITextField()
    private let status = UILabel()
    private var browser: WKWebView!
    private var observations: [NSKeyValueObservation] = []
    private var back: UIButton!
    private var forward: UIButton!

    private func button(_ title: String, symbol: String, action: UIAction) -> UIButton {
        let button = UIButton(type: .system)
        button.setImage(UIImage(systemName: symbol), for: .normal)
        button.accessibilityLabel = title
        button.addAction(action, for: .touchUpInside)
        button.widthAnchor.constraint(greaterThanOrEqualToConstant: 48).isActive = true
        button.heightAnchor.constraint(greaterThanOrEqualToConstant: 48).isActive = true
        return button
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        view.tintColor = UIColor(red: 0.64, green: 0.94, blue: 0.81, alpha: 1)
        let configuration = WKWebViewConfiguration()
        // Standard persistent WebKit data store and platform TLS/Safe Browsing.
        // No authentication-challenge override or arbitrary-loads ATS exception.
        browser = WKWebView(frame: .zero, configuration: configuration)
        browser.navigationDelegate = self
        browser.allowsBackForwardNavigationGestures = true
        address.placeholder = "HTTPS address or search"
        address.accessibilityLabel = "Address or search"
        address.accessibilityIdentifier = "forge-address"
        address.borderStyle = .roundedRect
        address.autocapitalizationType = .none
        address.autocorrectionType = .no
        address.keyboardType = .webSearch
        address.returnKeyType = .go
        address.delegate = self
        let go = button("Go", symbol: "arrow.right", action: UIAction { [weak self] _ in self?.navigate() })
        let toolbar = UIStackView(arrangedSubviews: [address, go])
        status.text = "WebKit prototype — HTTPS only. Not desktop Forge."
        status.font = .preferredFont(forTextStyle: .caption1)
        status.textColor = .secondaryLabel
        status.numberOfLines = 0
        status.accessibilityIdentifier = "forge-status"
        back = button("Back", symbol: "chevron.left", action: UIAction { [weak self] _ in self?.browser.goBack() })
        forward = button("Forward", symbol: "chevron.right", action: UIAction { [weak self] _ in self?.browser.goForward() })
        let reload = button("Reload", symbol: "arrow.clockwise", action: UIAction { [weak self] _ in self?.browser.reload() })
        let navigation = UIStackView(arrangedSubviews: [back, forward, reload])
        navigation.distribution = .fillEqually
        let stack = UIStackView(arrangedSubviews: [toolbar, status, browser, navigation])
        stack.axis = .vertical
        stack.spacing = 6
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 8),
            stack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -8),
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            stack.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor)
        ])
        observations = [
            browser.observe(\.url, options: [.new]) { [weak self] view, _ in self?.address.text = view.url?.absoluteString },
            browser.observe(\.canGoBack, options: [.initial, .new]) { [weak self] view, _ in self?.back.isEnabled = view.canGoBack },
            browser.observe(\.canGoForward, options: [.initial, .new]) { [weak self] view, _ in self?.forward.isEnabled = view.canGoForward }
        ]
        // Stay local until the person enters an address; no startup request.
    }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool { navigate(); return true }

    private func navigate() {
        guard let url = NavigationPolicy.input(address.text ?? "") else {
            status.text = "Unsupported address. Only HTTPS is enabled."
            return
        }
        address.resignFirstResponder()
        browser.load(URLRequest(url: url))
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url, NavigationPolicy.allows(url) else {
            status.text = "Unsupported navigation. No external app was opened."
            decisionHandler(.cancel)
            return
        }
        // Popup windows and downloads are intentionally unsupported in this prototype.
        decisionHandler(action.targetFrame == nil ? .cancel : .allow)
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) { status.text = "Loading…" }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { status.text = "Page loaded" }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        status.text = "Page could not be loaded. No certificate exception was added."
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        status.text = "Page could not be loaded."
    }
}
