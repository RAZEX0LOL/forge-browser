/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import UIKit
import WebKit

final class BrowserController: UIViewController, WKNavigationDelegate, WKUIDelegate, UITextFieldDelegate {
    private let address = UITextField()
    private let status = UILabel()
    private var browser: WKWebView!
    private var back: UIButton!
    private var forward: UIButton!
    private var addressAction: UIButton!
    private var reloadButton: UIButton!
    private var tabsButton: UIButton!
    private let tabsCount = UILabel()
    private let start = BrowserStartView()
    private let dock = UIView()
    private let navigation = UIStackView()
    private let addressSymbol = UIImageView(image: UIImage(systemName: "magnifyingglass"))
    private let addressContainer = UIView()
    private let pageProgress = UIProgressView(progressViewStyle: .bar)
    private var startedPages = Set<UUID>()
    private var keyboardDock: NSLayoutConstraint!
    private var safeAreaDock: NSLayoutConstraint!
    private var followsVisibleKeyboard = false
    private var webContainer = UIView()
    private var pages: [UUID: WKWebView] = [:]
    private var pageObservations: [UUID: [NSKeyValueObservation]] = [:]
    private let sessionStore: BrowserSessionStore
    private let libraryStore: BrowserLibraryStore
    private let regularDataStore: WKWebsiteDataStore
    private let siteDataClearer: @MainActor ([WKWebsiteDataStore], @escaping (Bool) -> Void) -> Void
    private static let controllers = NSHashTable<BrowserController>.weakObjects()
    private static var clearingOperation: UUID?
    var isClearingSiteData: Bool { Self.clearingOperation != nil }
    private var regularSession = BrowserSession()
    private var lastPersistedRegularSession: BrowserSession?
    private var privateSession = BrowserSession()
    private(set) var isPrivateBrowsing = false
    private var privateDataStore = WKWebsiteDataStore.nonPersistent()
    private var privacyCover: UIView?
    private var session: BrowserSession {
        get { isPrivateBrowsing ? privateSession : regularSession }
        set { if isPrivateBrowsing { privateSession = newValue } else { regularSession = newValue } }
    }
    private var persistenceEnabled = true
    private var statusKey = "WebKit prototype — HTTPS only. Not desktop Forge."
    private lazy var downloads = BrowserDownloads(presenter: self)
    private let mediaPermissions = BrowserMediaPermissions()
    private var mediaPages = Set<UUID>()
    private var permissionVersion = 0

    var sessionSnapshot: BrowserSession { session }

    init(sessionStore: BrowserSessionStore = BrowserSessionStore(),
         libraryStore: BrowserLibraryStore? = nil,
         dataStore: WKWebsiteDataStore = .default(),
         siteDataClearer: @escaping @MainActor ([WKWebsiteDataStore], @escaping (Bool) -> Void) -> Void = BrowserSiteData.clear) {
        self.sessionStore = sessionStore
        self.libraryStore = libraryStore ?? .shared
        self.regularDataStore = dataStore
        self.siteDataClearer = siteDataClearer
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { return nil }

    deinit { NotificationCenter.default.removeObserver(self) }

    private func text(_ key: String) -> String { NSLocalizedString(key, comment: "Forge mobile UI") }

    private func button(_ title: String, symbol: String, action: UIAction) -> UIButton {
        let button = UIButton(type: .system)
        var configuration = UIButton.Configuration.plain()
        configuration.image = UIImage(systemName: symbol)
        configuration.preferredSymbolConfigurationForImage = UIImage.SymbolConfiguration(pointSize: 21, weight: .regular)
        configuration.contentInsets = NSDirectionalEdgeInsets(top: 10, leading: 8, bottom: 10, trailing: 8)
        configuration.baseForegroundColor = BrowserPalette.foreground
        button.configuration = configuration
        button.configurationUpdateHandler = { control in
            control.configuration?.baseForegroundColor = control.isEnabled ? BrowserPalette.foreground : BrowserPalette.disabled
        }
        button.accessibilityLabel = text(title)
        button.addAction(action, for: .touchUpInside)
        button.widthAnchor.constraint(greaterThanOrEqualToConstant: 44).isActive = true
        let height = button.heightAnchor.constraint(greaterThanOrEqualToConstant: 44)
        height.priority = UILayoutPriority(999)
        height.isActive = true
        return button
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        Self.controllers.add(self)
        view.backgroundColor = BrowserPalette.background
        view.tintColor = BrowserPalette.accent
        overrideUserInterfaceStyle = .dark
        do {
            if let saved = try sessionStore.load() {
                session = saved
                lastPersistedRegularSession = saved
            } else { session = BrowserSession() }
        }
        catch { persistenceEnabled = false }
        address.attributedPlaceholder = NSAttributedString(string: text("Search or enter address"), attributes: [
            .foregroundColor: BrowserPalette.secondary
        ])
        address.accessibilityLabel = text("Address or search")
        address.accessibilityIdentifier = "forge-address"
        address.borderStyle = .none
        address.textColor = BrowserPalette.foreground
        address.tintColor = BrowserPalette.accent
        address.font = .preferredFont(forTextStyle: .body)
        address.adjustsFontForContentSizeCategory = true
        address.clearButtonMode = .whileEditing
        address.setContentHuggingPriority(.defaultLow, for: .horizontal)
        address.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        address.autocapitalizationType = .none
        address.autocorrectionType = .no
        address.keyboardType = .webSearch
        address.returnKeyType = .go
        address.delegate = self
        let go = button("Go", symbol: "arrow.right", action: UIAction { [weak self] _ in
            guard let self = self else { return }
            if self.address.isFirstResponder { self.cancelAddressEditing() } else { self.navigate() }
        })
        addressAction = go
        go.accessibilityIdentifier = "forge-go"
        go.configurationUpdateHandler = nil
        go.configuration?.baseForegroundColor = BrowserPalette.background
        go.configuration?.background.backgroundColor = BrowserPalette.accent
        go.configuration?.background.cornerRadius = 13
        go.widthAnchor.constraint(equalToConstant: 44).isActive = true
        go.heightAnchor.constraint(equalToConstant: 44).isActive = true
        addressSymbol.tintColor = BrowserPalette.secondary
        addressSymbol.contentMode = .scaleAspectFit
        addressSymbol.isAccessibilityElement = false
        addressSymbol.widthAnchor.constraint(equalToConstant: 20).isActive = true
        addressContainer.backgroundColor = BrowserPalette.field
        addressContainer.layer.cornerRadius = 19
        addressContainer.layer.borderWidth = 1
        addressContainer.layer.borderColor = BrowserPalette.border.cgColor
        addressContainer.accessibilityIdentifier = "forge-address-bar"
        let toolbar = UIStackView(arrangedSubviews: [addressSymbol, address, go])
        toolbar.alignment = .center
        toolbar.spacing = 10
        toolbar.translatesAutoresizingMaskIntoConstraints = false
        addressContainer.addSubview(toolbar)
        NSLayoutConstraint.activate([
            toolbar.leadingAnchor.constraint(equalTo: addressContainer.leadingAnchor, constant: 14),
            toolbar.trailingAnchor.constraint(equalTo: addressContainer.trailingAnchor, constant: -6),
            toolbar.topAnchor.constraint(equalTo: addressContainer.topAnchor, constant: 6),
            toolbar.bottomAnchor.constraint(equalTo: addressContainer.bottomAnchor, constant: -6),
            addressContainer.heightAnchor.constraint(greaterThanOrEqualToConstant: 56)
        ])
        status.font = .preferredFont(forTextStyle: .caption1)
        status.adjustsFontForContentSizeCategory = true
        status.textColor = UIColor(red: 1, green: 0.76, blue: 0.67, alpha: 1)
        status.numberOfLines = 0
        status.accessibilityIdentifier = "forge-status"
        back = button("Back", symbol: "chevron.left", action: UIAction { [weak self] _ in self?.browser?.goBack() })
        back.accessibilityIdentifier = "forge-back"
        forward = button("Forward", symbol: "chevron.right", action: UIAction { [weak self] _ in self?.browser?.goForward() })
        forward.accessibilityIdentifier = "forge-forward"
        let reload = button("Reload", symbol: "arrow.clockwise", action: UIAction { [weak self] _ in
            guard let self = self else { return }
            if self.browser?.isLoading == true { self.stopLoadingSelected() } else { self.reloadSelected() }
        })
        reloadButton = reload
        reload.accessibilityIdentifier = "forge-reload"
        let newTab = button("New tab", symbol: "plus", action: UIAction { [weak self] _ in self?.addTab() })
        newTab.accessibilityIdentifier = "forge-new-tab"
        tabsButton = button("Tabs", symbol: "square.on.square", action: UIAction { [weak self] _ in self?.showTabs() })
        tabsButton.accessibilityIdentifier = "forge-tabs"
        let menu = button("Browser menu", symbol: "ellipsis", action: UIAction { [weak self] _ in self?.showMenu() })
        menu.accessibilityIdentifier = "forge-menu"
        tabsButton.configuration?.image = nil
        let badge = UIView()
        badge.isUserInteractionEnabled = false
        badge.layer.cornerRadius = 6
        badge.layer.borderWidth = 1.5
        badge.layer.borderColor = BrowserPalette.foreground.cgColor
        tabsCount.font = .systemFont(ofSize: 13, weight: .semibold)
        tabsCount.textColor = BrowserPalette.foreground
        tabsCount.textAlignment = .center
        for element in [badge, tabsCount] { element.translatesAutoresizingMaskIntoConstraints = false }
        badge.addSubview(tabsCount)
        tabsButton.addSubview(badge)
        NSLayoutConstraint.activate([
            badge.widthAnchor.constraint(equalToConstant: 25), badge.heightAnchor.constraint(equalToConstant: 27),
            badge.centerXAnchor.constraint(equalTo: tabsButton.centerXAnchor),
            badge.centerYAnchor.constraint(equalTo: tabsButton.centerYAnchor),
            tabsCount.leadingAnchor.constraint(equalTo: badge.leadingAnchor), tabsCount.trailingAnchor.constraint(equalTo: badge.trailingAnchor),
            tabsCount.topAnchor.constraint(equalTo: badge.topAnchor), tabsCount.bottomAnchor.constraint(equalTo: badge.bottomAnchor)
        ])
        for control in [back!, forward!, newTab, reload, tabsButton!, menu] { navigation.addArrangedSubview(control) }
        navigation.distribution = .fillEqually
        navigation.spacing = 4
        navigation.accessibilityIdentifier = "forge-navigation"
        let rowHeight = navigation.heightAnchor.constraint(equalToConstant: 48)
        rowHeight.priority = UILayoutPriority(999)
        rowHeight.isActive = true
        pageProgress.progressTintColor = BrowserPalette.accent
        pageProgress.trackTintColor = BrowserPalette.border
        pageProgress.isHidden = true
        let progressHeight = pageProgress.heightAnchor.constraint(equalToConstant: 2)
        progressHeight.priority = UILayoutPriority(999)
        progressHeight.isActive = true
        let stack = UIStackView(arrangedSubviews: [downloads.panel, status, pageProgress, addressContainer, navigation])
        stack.axis = .vertical
        stack.spacing = 8
        stack.translatesAutoresizingMaskIntoConstraints = false
        dock.backgroundColor = BrowserPalette.surface
        dock.accessibilityIdentifier = "forge-browser-dock"
        dock.translatesAutoresizingMaskIntoConstraints = false
        webContainer.backgroundColor = BrowserPalette.background
        webContainer.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webContainer)
        view.addSubview(dock)
        dock.addSubview(stack)
        let border = UIView()
        border.backgroundColor = BrowserPalette.border
        border.translatesAutoresizingMaskIntoConstraints = false
        dock.addSubview(border)
        let preferredWidth = stack.widthAnchor.constraint(equalTo: view.safeAreaLayoutGuide.widthAnchor, constant: -24)
        preferredWidth.priority = .defaultHigh
        start.translatesAutoresizingMaskIntoConstraints = false
        webContainer.addSubview(start)
        start.onSearch = { [weak self] in self?.address.becomeFirstResponder() }
        start.onTabs = { [weak self] in self?.showTabs() }
        start.onRestore = { [weak self] in self?.reloadSelected() }
        keyboardDock = dock.bottomAnchor.constraint(equalTo: view.keyboardLayoutGuide.topAnchor)
        keyboardDock.priority = UILayoutPriority(999)
        safeAreaDock = dock.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor)
        NSLayoutConstraint.activate([
            webContainer.leadingAnchor.constraint(equalTo: view.leadingAnchor), webContainer.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            webContainer.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webContainer.bottomAnchor.constraint(equalTo: dock.topAnchor),
            dock.leadingAnchor.constraint(equalTo: view.leadingAnchor), dock.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            safeAreaDock, keyboardDock,
            dock.bottomAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.bottomAnchor),
            stack.leadingAnchor.constraint(greaterThanOrEqualTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 12),
            stack.trailingAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -12),
            stack.centerXAnchor.constraint(equalTo: view.safeAreaLayoutGuide.centerXAnchor),
            stack.widthAnchor.constraint(lessThanOrEqualToConstant: 700), preferredWidth,
            stack.topAnchor.constraint(equalTo: dock.topAnchor, constant: 12),
            stack.bottomAnchor.constraint(equalTo: dock.bottomAnchor, constant: -8),
            border.topAnchor.constraint(equalTo: dock.topAnchor), border.leadingAnchor.constraint(equalTo: dock.leadingAnchor),
            border.trailingAnchor.constraint(equalTo: dock.trailingAnchor), border.heightAnchor.constraint(equalToConstant: 0.5),
            start.leadingAnchor.constraint(equalTo: webContainer.leadingAnchor), start.trailingAnchor.constraint(equalTo: webContainer.trailingAnchor),
            start.topAnchor.constraint(equalTo: webContainer.topAnchor), start.bottomAnchor.constraint(equalTo: webContainer.bottomAnchor)
        ])
        if isClearingSiteData { view.isUserInteractionEnabled = false; showStatus("Clearing site data…") }
        else { activateSelected(loadSavedPage: false) }
        NotificationCenter.default.addObserver(self, selector: #selector(saveForBackground),
                                               name: UIApplication.didEnterBackgroundNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(keyboardWillChange(_:)),
                                               name: UIResponder.keyboardWillChangeFrameNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(coverPrivateContent),
                                               name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(uncoverPrivateContent),
                                               name: UIApplication.didBecomeActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(sceneWillDeactivate(_:)),
                                               name: UIScene.willDeactivateNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(sceneDidActivate(_:)),
                                               name: UIScene.didActivateNotification, object: nil)
    }

    @objc private func sceneWillDeactivate(_ notification: Notification) {
        guard let scene = notification.object as? UIScene, scene === view.window?.windowScene else { return }
        coverPrivateContent()
    }

    @objc private func sceneDidActivate(_ notification: Notification) {
        guard let scene = notification.object as? UIScene, scene === view.window?.windowScene else { return }
        uncoverPrivateContent()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        mediaPermissions.cancel()
        stopMediaPages()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if browser == nil && !isClearingSiteData { activateSelected(loadSavedPage: false) }
    }

    @objc private func coverPrivateContent() {
        permissionVersion += 1
        mediaPermissions.resignActive()
        stopMediaPages()
        guard isPrivateBrowsing, privacyCover == nil else { return }
        let cover = UIView(frame: view.bounds)
        cover.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        cover.backgroundColor = BrowserPalette.background
        cover.accessibilityLabel = text("Private browsing")
        cover.accessibilityIdentifier = "forge-privacy-cover"
        view.addSubview(cover)
        privacyCover = cover
    }

    @objc private func uncoverPrivateContent() {
        privacyCover?.removeFromSuperview()
        privacyCover = nil
        mediaPermissions.resume()
        if isViewLoaded, browser == nil, !isClearingSiteData { activateSelected(loadSavedPage: false) }
    }

    @objc private func keyboardWillChange(_ notification: Notification) {
        guard let window = view.window, window.isKeyWindow,
              let frame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect else { return }
        let local = view.convert(window.convert(frame, from: nil), from: window)
        let overlap = view.bounds.intersection(local)
        let visible = !overlap.isNull && overlap.height > view.safeAreaInsets.bottom + 1
            && local.maxY >= view.bounds.maxY - view.safeAreaInsets.bottom - 1
        guard visible != followsVisibleKeyboard else { return }
        followsVisibleKeyboard = visible
        safeAreaDock.isActive = !visible
        let duration = (notification.userInfo?[UIResponder.keyboardAnimationDurationUserInfoKey] as? NSNumber)?.doubleValue ?? 0
        let curve = (notification.userInfo?[UIResponder.keyboardAnimationCurveUserInfoKey] as? NSNumber)?.uintValue ?? 0
        UIView.animate(withDuration: duration, delay: 0,
                       options: [UIView.AnimationOptions(rawValue: curve << 16), .beginFromCurrentState, .allowUserInteraction]) {
            self.view.layoutIfNeeded()
        }
    }

    private func showStatus(_ key: String) {
        statusKey = key
        let libraryWarning = "Library storage is unavailable. Existing data was not changed."
        status.text = text(key) + (persistenceEnabled ? "" : "\n" + text("Session storage is unavailable. Existing saved data was not changed."))
            + (libraryStore.isAvailable || key == libraryWarning ? "" : "\n" + text(libraryWarning))
        status.isHidden = persistenceEnabled && libraryStore.isAvailable && ["WebKit prototype — HTTPS only. Not desktop Forge.", "Loading…", "Page loaded",
            "Saved tab restored. Tap Reload to load the page."].contains(key)
    }

    private func persistSession() {
        // Private activity and unchanged WebKit observations must not rewrite the
        // regular snapshot (JSON key ordering is not byte-stable across encodings).
        guard persistenceEnabled, regularSession != lastPersistedRegularSession else { return }
        do {
            try sessionStore.save(regularSession)
            lastPersistedRegularSession = regularSession
        }
        catch { persistenceEnabled = false; showStatus(statusKey) }
    }

    @objc private func saveForBackground() {
        mediaPermissions.cancel()
        stopMediaPages()
        persistSession()
    }

    private func stopMediaPages(keeping selected: UUID? = nil) {
        for id in Array(mediaPages) where id != selected {
            pageObservations.removeValue(forKey: id)
            startedPages.remove(id)
            mediaPages.remove(id)
            guard let page = pages.removeValue(forKey: id) else { continue }
            page.uiDelegate = BrowserDeniedPermissions.shared
            page.navigationDelegate = nil
            page.setCameraCaptureState(.none)
            page.setMicrophoneCaptureState(.none)
            page.stopLoading()
            page.loadHTMLString("", baseURL: nil)
            page.removeFromSuperview()
            if page === browser { browser = nil }
        }
    }

    private func page(for tab: BrowserTab) -> WKWebView {
        if let existing = pages[tab.id] { return existing }
        let configuration = WKWebViewConfiguration()
        let privatePage = isPrivateBrowsing
        configuration.websiteDataStore = privatePage ? privateDataStore : regularDataStore
        // Standard persistent WebKit data store and platform TLS/Safe Browsing.
        // No authentication-challenge override or arbitrary-loads ATS exception.
        let page = WKWebView(frame: .zero, configuration: configuration)
        page.navigationDelegate = self
        page.uiDelegate = self
        page.allowsBackForwardNavigationGestures = true
        page.isFindInteractionEnabled = true
        page.isOpaque = false
        page.backgroundColor = BrowserPalette.background
        page.scrollView.backgroundColor = BrowserPalette.background
        page.underPageBackgroundColor = BrowserPalette.background
        pages[tab.id] = page
        pageObservations[tab.id] = [
            page.observe(\.url, options: [.new]) { [weak self] view, _ in
                guard let self = self, let url = view.url, NavigationPolicy.allows(url) else { return }
                if privatePage { self.privateSession.update(tab.id, url: url.absoluteString) }
                else { self.regularSession.update(tab.id, url: url.absoluteString) }
                self.persistSession()
                if self.session.selectedID == tab.id { self.refreshControls() }
            },
            page.observe(\.title, options: [.new]) { [weak self] view, _ in
                guard let self = self else { return }
                if privatePage { self.privateSession.update(tab.id, title: view.title ?? "") }
                else { self.regularSession.update(tab.id, title: view.title ?? "") }
                self.persistSession()
            },
            page.observe(\.canGoBack, options: [.new]) { [weak self] _, _ in self?.refreshControls() },
            page.observe(\.canGoForward, options: [.new]) { [weak self] _, _ in self?.refreshControls() },
            page.observe(\.estimatedProgress, options: [.new]) { [weak self] _, _ in self?.refreshProgress() },
            page.observe(\.isLoading, options: [.new]) { [weak self] _, _ in self?.refreshProgress() }
        ]
        return page
    }

    private func refreshControls() {
        guard let browser = browser, !isClearingSiteData else { return }
        if !address.isFirstResponder {
            address.text = session.selectedTab.url == "about:blank" ? "" : session.selectedTab.url
        }
        back.isEnabled = browser.canGoBack
        forward.isEnabled = browser.canGoForward
        let count = String(format: text("Tabs (%ld)"), session.tabs.count)
        tabsCount.text = String(session.tabs.count)
        tabsButton.accessibilityLabel = isPrivateBrowsing ? text("Private browsing") + ": " + count : count
        address.accessibilityHint = isPrivateBrowsing ? text("Private browsing") : nil
        addressSymbol.tintColor = isPrivateBrowsing ? .systemPurple : BrowserPalette.secondary
        tabsCount.text = (isPrivateBrowsing ? "P" : "") + String(session.tabs.count)
        updatePagePresentation()
    }

    private func refreshProgress() {
        guard let browser = browser else { return }
        pageProgress.progress = Float(browser.estimatedProgress)
        pageProgress.isHidden = !browser.isLoading
        reloadButton.configuration?.image = UIImage(systemName: browser.isLoading ? "xmark" : "arrow.clockwise")
        reloadButton.accessibilityLabel = text(browser.isLoading ? "Stop loading" : "Reload")
        reloadButton.accessibilityIdentifier = browser.isLoading ? "forge-stop" : "forge-reload"
    }

    private func updatePagePresentation() {
        guard let browser = browser, !isClearingSiteData else { return }
        let tab = session.selectedTab
        let native = tab.url == "about:blank" || (browser.url == nil && !startedPages.contains(tab.id))
        start.configure(tab: tab, count: session.tabs.count)
        start.isHidden = !native
        browser.isHidden = native
        addressSymbol.image = UIImage(systemName: tab.url == "about:blank" || address.isFirstResponder ? "magnifyingglass" : "globe")
        refreshProgress()
    }

    private func activateSelected(loadSavedPage: Bool) {
        guard !isClearingSiteData else { return }
        browser?.findInteraction?.dismissFindNavigator()
        mediaPermissions.cancel()
        permissionVersion += 1
        stopMediaPages(keeping: session.selectedID)
        address.resignFirstResponder()
        browser?.removeFromSuperview()
        let tab = session.selectedTab
        browser = page(for: tab)
        browser.translatesAutoresizingMaskIntoConstraints = false
        webContainer.addSubview(browser)
        webContainer.bringSubviewToFront(start)
        NSLayoutConstraint.activate([
            browser.leadingAnchor.constraint(equalTo: webContainer.leadingAnchor),
            browser.trailingAnchor.constraint(equalTo: webContainer.trailingAnchor),
            browser.topAnchor.constraint(equalTo: webContainer.topAnchor),
            browser.bottomAnchor.constraint(equalTo: webContainer.bottomAnchor)
        ])
        refreshControls()
        if browser.url == nil && tab.url != "about:blank" {
            showStatus("Saved tab restored. Tap Reload to load the page.")
            if loadSavedPage { reloadSelected() }
        } else { showStatus("WebKit prototype — HTTPS only. Not desktop Forge.") }
    }

    @discardableResult func addTab() -> Bool {
        guard !isClearingSiteData else { return false }
        guard session.addTab() != nil else { showStatus("Tab limit reached (32)."); return false }
        persistSession()
        activateSelected(loadSavedPage: false)
        return true
    }

    func selectTab(_ id: UUID) {
        guard !isClearingSiteData else { return }
        guard session.select(id) else { return }
        persistSession()
        activateSelected(loadSavedPage: true)
    }

    func closeTab(_ id: UUID, loadSavedPage: Bool = true) {
        guard !isClearingSiteData else { return }
        mediaPermissions.cancel()
        permissionVersion += 1
        guard session.tabs.contains(where: { $0.id == id }) else { return }
        let wasSelected = session.selectedID == id
        session.close(id)
        startedPages.remove(id)
        mediaPages.remove(id)
        pageObservations.removeValue(forKey: id)
        if let removed = pages.removeValue(forKey: id) {
            removed.navigationDelegate = nil
            removed.uiDelegate = BrowserDeniedPermissions.shared
            removed.setCameraCaptureState(.none)
            removed.setMicrophoneCaptureState(.none)
            removed.stopLoading()
            removed.removeFromSuperview()
        }
        persistSession()
        if wasSelected { activateSelected(loadSavedPage: loadSavedPage) } else { refreshControls() }
    }

    private func reloadSelected() {
        guard !isClearingSiteData else { return }
        guard session.selectedTab.url != "about:blank" else { return }
        startedPages.insert(session.selectedID)
        updatePagePresentation()
        if browser.url == nil {
            guard let url = URL(string: session.selectedTab.url), NavigationPolicy.allows(url) else { return }
            browser.load(URLRequest(url: url))
        } else { browser.reload() }
    }

    private func showTabs() {
        guard !isClearingSiteData else { return }
        guard presentedViewController == nil else { return }
        mediaPermissions.cancel()
        stopMediaPages()
        address.resignFirstResponder()
        view.layoutIfNeeded()
        let overview = BrowserTabsController(snapshot: { [weak self] in
            guard let self = self else { return BrowserTabsSnapshot(tabs: [], selectedID: UUID(), isPrivate: false) }
            return BrowserTabsSnapshot(tabs: self.session.tabs, selectedID: self.session.selectedID, isPrivate: self.isPrivateBrowsing)
        }, select: { [weak self] in self?.selectTab($0) },
           close: { [weak self] in self?.closeTab($0, loadSavedPage: false) },
           addTab: { [weak self] in self?.addTab() },
           changeMode: { [weak self] in self?.setPrivateBrowsing($0) },
           closePrivate: { [weak self] in self?.closePrivateTabs() })
        let navigation = UINavigationController(rootViewController: overview)
        navigation.overrideUserInterfaceStyle = .dark
        navigation.view.tintColor = BrowserPalette.accent
        navigation.modalPresentationStyle = .fullScreen
        present(navigation, animated: true)
    }

    private func showMenu() {
        guard !isClearingSiteData, presentedViewController == nil else { return }
        address.resignFirstResponder()
        let sheet = UIAlertController(title: text("Browser menu"), message: nil, preferredStyle: .actionSheet)
        func addAction(_ title: String, enabled: Bool = true, perform: @escaping () -> Void) {
            let action = UIAlertAction(title: text(title), style: .default) { [weak sheet] _ in
                sheet?.dismiss(animated: true, completion: perform)
            }
            action.isEnabled = enabled
            sheet.addAction(action)
        }
        addAction("Share link", enabled: BrowserLinkActions.shareURL(session.selectedTab.url) != nil) { [weak self] in
            self?.requestShareSelected()
        }
        addAction("Find in page", enabled: browser?.isHidden == false && browser?.url != nil) { [weak self] in
            self?.findInSelectedPage()
        }
        addAction("Bookmarks") { [weak self] in self?.showLibrary(bookmarks: true) }
        addAction("History") { [weak self] in self?.showLibrary(bookmarks: false) }
        addAction("Add bookmark", enabled: !isPrivateBrowsing && libraryStore.isAvailable
                  && BrowserLinkActions.shareURL(session.selectedTab.url) != nil) { [weak self] in self?.bookmarkSelected() }
        sheet.addAction(UIAlertAction(title: text("Tabs"), style: .default) { [weak self, weak sheet] _ in
            sheet?.dismiss(animated: true) { self?.showTabs() }
        })
        sheet.addAction(UIAlertAction(title: text("New tab"), style: .default) { [weak self] _ in self?.addTab() })
        sheet.addAction(UIAlertAction(title: text(isPrivateBrowsing ? "Regular tabs" : "Private tabs"), style: .default) { [weak self] _ in
            guard let self = self else { return }
            self.setPrivateBrowsing(!self.isPrivateBrowsing)
        })
        sheet.addAction(UIAlertAction(title: text("Close current tab"), style: .destructive) { [weak self] _ in
            guard let self = self else { return }
            self.closeTab(self.session.selectedID)
        })
        sheet.addAction(UIAlertAction(title: text("Clear site data"), style: .destructive) { [weak self] _ in
            self?.requestClearSiteData()
        })
        sheet.addAction(UIAlertAction(title: text("Cancel"), style: .cancel))
        sheet.popoverPresentationController?.sourceView = tabsButton
        sheet.popoverPresentationController?.sourceRect = tabsButton.bounds
        present(sheet, animated: true)
    }

    func makeShareController() -> UIActivityViewController? {
        guard let url = BrowserLinkActions.shareURL(session.selectedTab.url) else { return nil }
        // The user chooses a destination; Forge never sends directly or shares a screenshot.
        let sheet = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        sheet.popoverPresentationController?.sourceView = tabsButton
        sheet.popoverPresentationController?.sourceRect = tabsButton.bounds
        return sheet
    }

    func makePrivateShareConfirmation() -> UIAlertController {
        let id = session.selectedID
        let url = session.selectedTab.url
        let version = permissionVersion
        let alert = UIAlertController(title: text("Share private link?"),
            message: text("Private sharing warning"), preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: text("Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: text("Continue"), style: .default) { [weak self, weak alert] _ in
            alert?.dismiss(animated: true) {
                guard let self = self, self.isPrivateBrowsing, self.session.selectedID == id,
                      self.session.selectedTab.url == url, self.permissionVersion == version else { return }
                self.presentShareSheet()
            }
        })
        alert.preferredAction = alert.actions.first
        return alert
    }

    private func presentShareSheet() {
        guard !isClearingSiteData, presentedViewController == nil,
              UIApplication.shared.applicationState == .active, view.window?.isKeyWindow == true,
              let sheet = makeShareController() else { return }
        present(sheet, animated: true)
    }

    private func requestShareSelected() {
        guard !isClearingSiteData, presentedViewController == nil else { return }
        if isPrivateBrowsing { present(makePrivateShareConfirmation(), animated: true) }
        else { presentShareSheet() }
    }

    func findInSelectedPage() {
        guard !isClearingSiteData, presentedViewController == nil, browser?.isHidden == false else { return }
        address.resignFirstResponder()
        browser.findInteraction?.presentFindNavigator(showingReplace: false)
    }

    private func showLibrary(bookmarks: Bool) {
        guard !isClearingSiteData, presentedViewController == nil else { return }
        mediaPermissions.cancel(); stopMediaPages(); address.resignFirstResponder()
        let library = BrowserLibraryController(store: libraryStore, bookmarks: bookmarks, privateMode: isPrivateBrowsing) { [weak self] url in
            guard let self = self, !self.isClearingSiteData, BrowserLinkActions.shareURL(url) != nil else { return }
            if self.browser == nil { self.activateSelected(loadSavedPage: false) }
            self.address.text = url; self.navigate()
        }
        let navigation = UINavigationController(rootViewController: library)
        navigation.overrideUserInterfaceStyle = .dark; navigation.view.tintColor = BrowserPalette.accent
        navigation.modalPresentationStyle = .fullScreen
        present(navigation, animated: true)
    }

    @discardableResult func bookmarkSelected() -> Bool {
        guard !isClearingSiteData else { return false }
        do {
            let tab = session.selectedTab
            let added = try libraryStore.addBookmark(url: tab.url, title: tab.title, isPrivate: isPrivateBrowsing)
            showStatus(added ? "Bookmark saved." : "Bookmark could not be added. Private pages and unsupported addresses are not saved; the limit is 200.")
            return added
        } catch { showStatus("Library storage is unavailable. Existing data was not changed."); return false }
    }

    func setPrivateBrowsing(_ enabled: Bool) {
        guard !isClearingSiteData else { return }
        guard enabled != isPrivateBrowsing else { return }
        address.resignFirstResponder()
        browser?.stopLoading()
        isPrivateBrowsing = enabled
        activateSelected(loadSavedPage: false)
    }

    func closePrivateTabs() {
        guard !isClearingSiteData else { return }
        mediaPermissions.cancel()
        for tab in privateSession.tabs {
            pageObservations.removeValue(forKey: tab.id)
            startedPages.remove(tab.id)
            mediaPages.remove(tab.id)
            if let page = pages.removeValue(forKey: tab.id) {
                page.navigationDelegate = nil
                page.uiDelegate = BrowserDeniedPermissions.shared
                page.setCameraCaptureState(.none)
                page.setMicrophoneCaptureState(.none)
                page.stopLoading()
                page.removeFromSuperview()
            }
        }
        privateSession = BrowserSession()
        privateDataStore = .nonPersistent()
        isPrivateBrowsing = false
        activateSelected(loadSavedPage: false)
    }

    func makeClearSiteDataConfirmation() -> UIAlertController {
        let alert = UIAlertController(title: text("Clear site data"), message: text("Clear site data warning"), preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: text("Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: text("Clear site data"), style: .destructive) { [weak self] _ in
            self?.clearSiteDataConfirmed()
        })
        alert.preferredAction = alert.actions.first
        return alert
    }

    private func requestClearSiteData() {
        guard !isClearingSiteData else { return }
        guard !Self.controllers.allObjects.contains(where: { $0.downloads.stage == .exporting }) else {
            showStatus("Finish exporting the file before clearing site data."); return
        }
        if let sheet = presentedViewController as? UIAlertController {
            sheet.dismiss(animated: true) { [weak self] in
                guard let self = self else { return }
                self.present(self.makeClearSiteDataConfirmation(), animated: true)
            }
        } else if presentedViewController == nil { present(makeClearSiteDataConfirmation(), animated: true) }
    }

    func clearSiteDataConfirmed(completion: ((Bool) -> Void)? = nil) {
        guard !isClearingSiteData else { completion?(false); return }
        let controllers = Self.controllers.allObjects
        guard !controllers.contains(where: { $0.downloads.stage == .exporting }) else {
            showStatus("Finish exporting the file before clearing site data.")
            completion?(false); return
        }
        let operation = UUID()
        Self.clearingOperation = operation
        var stores: [WKWebsiteDataStore] = []
        for controller in controllers {
            for store in [controller.regularDataStore, controller.privateDataStore]
                where !stores.contains(where: { $0 === store }) { stores.append(store) }
            controller.prepareForSiteDataClearing()
        }
        siteDataClearer(stores) { success in
            guard Self.clearingOperation == operation else { return }
            Self.clearingOperation = nil
            for controller in Self.controllers.allObjects {
                controller.view.isUserInteractionEnabled = true
                controller.activateSelected(loadSavedPage: false)
                controller.showStatus(success ? "Site data cleared." : "Site data could not be fully cleared. Try again.")
            }
            completion?(success)
        }
    }

    private func prepareForSiteDataClearing() {
        mediaPermissions.cancel()
        presentedViewController?.dismiss(animated: false)
        permissionVersion += 1
        view.endEditing(true)
        view.isUserInteractionEnabled = false
        downloads.cancel()
        pageObservations.removeAll()
        for page in pages.values {
            page.navigationDelegate = nil
            page.uiDelegate = BrowserDeniedPermissions.shared
            page.setCameraCaptureState(.none)
            page.setMicrophoneCaptureState(.none)
            page.stopLoading()
            page.removeFromSuperview()
        }
        browser = nil
        pages.removeAll()
        startedPages.removeAll()
        mediaPages.removeAll()
        privateSession = BrowserSession()
        privateDataStore = .nonPersistent()
        isPrivateBrowsing = false
        uncoverPrivateContent()
        start.configure(tab: regularSession.selectedTab, count: regularSession.tabs.count)
        start.isHidden = false
        address.text = ""
        back.isEnabled = false
        forward.isEnabled = false
        pageProgress.isHidden = true
        showStatus("Clearing site data…")
    }

    override func didReceiveMemoryWarning() {
        super.didReceiveMemoryWarning()
        for id in Array(pages.keys) where id != session.selectedID {
            pageObservations.removeValue(forKey: id)
            pages[id]?.navigationDelegate = nil
            pages[id]?.uiDelegate = BrowserDeniedPermissions.shared
            pages[id]?.setCameraCaptureState(.none)
            pages[id]?.setMicrophoneCaptureState(.none)
            pages[id]?.stopLoading()
            pages.removeValue(forKey: id)
            startedPages.remove(id)
            mediaPages.remove(id)
        }
    }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool { navigate(); return true }

    func textFieldDidBeginEditing(_ textField: UITextField) {
        navigation.isHidden = true
        addressContainer.layer.borderColor = BrowserPalette.accent.cgColor
        addressSymbol.image = UIImage(systemName: "magnifyingglass")
        textField.selectAll(nil)
        addressAction.configuration?.image = UIImage(systemName: "xmark")
        addressAction.accessibilityLabel = text("Cancel address editing")
        addressAction.accessibilityIdentifier = "forge-address-cancel"
    }

    func textFieldDidEndEditing(_ textField: UITextField) {
        navigation.isHidden = false
        addressContainer.layer.borderColor = BrowserPalette.border.cgColor
        address.text = session.selectedTab.url == "about:blank" ? "" : session.selectedTab.url
        addressAction.configuration?.image = UIImage(systemName: "arrow.right")
        addressAction.accessibilityLabel = text("Go")
        addressAction.accessibilityIdentifier = "forge-go"
        updatePagePresentation()
    }

    func cancelAddressEditing() {
        address.text = session.selectedTab.url == "about:blank" ? "" : session.selectedTab.url
        address.resignFirstResponder()
    }

    func stopLoadingSelected() {
        guard !isClearingSiteData else { return }
        mediaPermissions.cancel()
        permissionVersion += 1
        browser?.stopLoading()
        refreshProgress()
        showStatus("Loading stopped.")
    }

    private func navigate() {
        guard !isClearingSiteData else { return }
        mediaPermissions.cancel()
        permissionVersion += 1
        guard let url = NavigationPolicy.input(address.text ?? "") else {
            showStatus("Unsupported address. Only HTTPS is enabled.")
            return
        }
        address.resignFirstResponder()
        guard session.update(session.selectedID, url: url.absoluteString) else {
            showStatus("Unsupported address. Only HTTPS is enabled.")
            return
        }
        persistSession()
        startedPages.insert(session.selectedID)
        refreshControls()
        browser.load(URLRequest(url: url))
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard !isClearingSiteData, pages.values.contains(where: { $0 === webView }) else {
            decisionHandler(.cancel); return
        }
        guard let url = action.request.url, NavigationPolicy.allows(url) else {
            if webView === browser { showStatus("Unsupported navigation. No external app was opened.") }
            decisionHandler(.cancel)
            return
        }
        guard action.targetFrame != nil else {
            // Cancel WebKit's auxiliary window first. A separately created native
            // tab has no opener and never replays a form body or request headers.
            let explicitLink = action.navigationType == .linkActivated && action.sourceFrame.isMainFrame
                && action.request.httpMethod == "GET" && !action.shouldPerformDownload
            let version = permissionVersion
            decisionHandler(.cancel)
            guard explicitLink else { return }
            DispatchQueue.main.async { [weak self, weak webView] in
                guard let self = self, let source = webView, self.permissionVersion == version else { return }
                guard self.canOpenLinkInNewTab(url, from: source) else { return }
                // WKNavigationType alone is not proof of a trusted gesture:
                // synthetic anchor activation must not create tabs automatically.
                self.present(self.makeNewTabConfirmation(url, from: source), animated: true)
            }
            return
        }
        if action.targetFrame?.isMainFrame == true {
            mediaPermissions.cancel()
            permissionVersion += 1
        }
        if action.shouldPerformDownload && !webView.configuration.websiteDataStore.isPersistent {
            showStatus("Downloads are unavailable in private browsing.")
            decisionHandler(.cancel)
            return
        }
        decisionHandler(action.shouldPerformDownload && DownloadPolicy.allows(url) ? .download : .allow)
    }

    private func canOpenLinkInNewTab(_ url: URL, from source: WKWebView) -> Bool {
        return !isClearingSiteData && source === browser &&
              pages[session.selectedID] === source && !source.isHidden &&
              presentedViewController == nil && UIApplication.shared.applicationState == .active &&
              view.window?.isKeyWindow == true &&
              view.window?.windowScene?.activationState == .foregroundActive &&
              BrowserLinkActions.shareURL(source.url?.absoluteString ?? "") != nil &&
              BrowserLinkActions.shareURL(url.absoluteString) != nil
    }

    func makeNewTabConfirmation(_ url: URL, from source: WKWebView) -> UIAlertController {
        let version = permissionVersion
        let alert = UIAlertController(title: text("Open link in new tab"),
            message: text("New tab link warning"), preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: text("Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: text("Open link in new tab"), style: .default) { [weak self, weak source, weak alert] _ in
            alert?.dismiss(animated: true) {
                guard let self = self, let source = source, self.permissionVersion == version else { return }
                self.openLinkInNewTab(url, from: source)
            }
        })
        alert.preferredAction = alert.actions.first
        return alert
    }

    @discardableResult func openLinkInNewTab(_ url: URL, from source: WKWebView) -> Bool {
        guard canOpenLinkInNewTab(url, from: source) else { return false }
        guard addTab() else { return false }
        address.text = url.absoluteString
        navigate()
        return true
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        guard !isClearingSiteData, pages.values.contains(where: { $0 === webView }) else {
            decisionHandler(.cancel); return
        }
        guard let url = response.response.url, NavigationPolicy.allows(url) else {
            decisionHandler(.cancel)
            return
        }
        let disposition = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition") ?? ""
        let attachment = disposition.lowercased().trimmingCharacters(in: .whitespaces).hasPrefix("attachment")
        let needsDownload = attachment || !response.canShowMIMEType
        if needsDownload {
            let privatePage = !webView.configuration.websiteDataStore.isPersistent
            if privatePage { showStatus("Downloads are unavailable in private browsing.") }
            decisionHandler(!privatePage && response.isForMainFrame && webView === browser && DownloadPolicy.allows(url) ? .download : .cancel)
        } else { decisionHandler(.allow) }
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        guard !isClearingSiteData, webView === browser, webView.configuration.websiteDataStore.isPersistent else { download.cancel(nil); return }
        downloads.attach(download)
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        guard !isClearingSiteData, webView === browser, webView.configuration.websiteDataStore.isPersistent else { download.cancel(nil); return }
        downloads.attach(download)
    }

    private func permissionOrigin(_ origin: WKSecurityOrigin) -> String? {
        var components = URLComponents()
        components.scheme = origin.protocol
        components.host = origin.host
        components.port = origin.port == 0 ? nil : origin.port
        return BrowserPermissionPolicy.origin(components.string)
    }

    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        guard let site = permissionOrigin(origin), site == permissionOrigin(frame.securityOrigin),
              site == BrowserPermissionPolicy.origin(webView.url?.absoluteString),
              webView === browser, !webView.isLoading, webView.hasOnlySecureContent,
               !isClearingSiteData, presentedViewController == nil else { decisionHandler(.deny); return }
        let camera: Bool
        let microphone: Bool
        switch type {
        case .camera: camera = true; microphone = false
        case .microphone: camera = false; microphone = true
        case .cameraAndMicrophone: camera = true; microphone = true
        @unknown default: decisionHandler(.deny); return
        }
        let id = session.selectedID
        let version = permissionVersion
        let valid = { [weak self, weak webView] in
            guard let self = self, let page = webView else { return false }
            return !self.isClearingSiteData && self.presentedViewController == nil
                && self.permissionVersion == version && self.browser === page
                && self.pages[id] === page && self.session.selectedID == id && page.hasOnlySecureContent && !page.isLoading
                && self.view.window?.isKeyWindow == true && self.view.window?.windowScene?.activationState == .foregroundActive
                && BrowserPermissionPolicy.origin(page.url?.absoluteString) == site
        }
        mediaPermissions.request(site: site, camera: camera, microphone: microphone, presenter: self, valid: valid) { [weak self] allowed in
            if allowed { self?.mediaPages.insert(id) }
            else { self?.showStatus("Camera or microphone access was not granted.") }
            decisionHandler(allowed ? .grant : .deny)
        }
    }

    func webView(_ webView: WKWebView, requestDeviceOrientationAndMotionPermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(.deny)
    }

    @available(iOS 27.0, *)
    func webView(_ webView: WKWebView, requestGeolocationPermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(.deny)
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        if webView === browser {
            startedPages.insert(session.selectedID)
            showStatus("Loading…")
            updatePagePresentation()
        }
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if webView === browser { showStatus("Page loaded"); refreshControls() }
        guard !isClearingSiteData, let id = pages.first(where: { $0.value === webView })?.key,
              regularSession.tabs.contains(where: { $0.id == id }), let url = webView.url else { return }
        do { try libraryStore.recordVisit(url: url.absoluteString, title: webView.title ?? "", isPrivate: false) }
        catch { if webView === browser { showStatus("Library storage is unavailable. Existing data was not changed.") } }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if webView === browser, let message = BrowserNavigationError.message(for: error) {
            showStatus(message)
            refreshProgress()
        }
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        if webView === browser, let message = BrowserNavigationError.message(for: error) {
            showStatus(message)
            refreshProgress()
        }
    }
}
