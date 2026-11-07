/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import UIKit

struct BrowserTabsSnapshot {
    let tabs: [BrowserTab]
    let selectedID: UUID
    let isPrivate: Bool

    func matching(_ query: String) -> [BrowserTab] {
        let query = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return tabs }
        return tabs.filter { $0.title.localizedCaseInsensitiveContains(query) || $0.url.localizedCaseInsensitiveContains(query) }
    }
}

// Text-only overview: no website requests or screenshots are made for tab previews.
final class BrowserTabsController: UITableViewController, UISearchBarDelegate {
    private let snapshot: () -> BrowserTabsSnapshot
    private let select: (UUID) -> Void
    private let close: (UUID) -> Void
    private let addTab: () -> Void
    private let changeMode: (Bool) -> Void
    private let closePrivate: () -> Void
    private let search = UISearchBar()
    private let modes = UISegmentedControl()
    private let empty = UILabel()
    private var visibleTabs: [BrowserTab] = []
    private var privacyCover: UIView?

    init(snapshot: @escaping () -> BrowserTabsSnapshot, select: @escaping (UUID) -> Void,
         close: @escaping (UUID) -> Void, addTab: @escaping () -> Void,
         changeMode: @escaping (Bool) -> Void, closePrivate: @escaping () -> Void) {
        self.snapshot = snapshot
        self.select = select
        self.close = close
        self.addTab = addTab
        self.changeMode = changeMode
        self.closePrivate = closePrivate
        super.init(style: .insetGrouped)
    }

    required init?(coder: NSCoder) { return nil }
    deinit { NotificationCenter.default.removeObserver(self) }
    private func text(_ key: String) -> String { NSLocalizedString(key, comment: "Forge tabs") }

    override func viewDidLoad() {
        super.viewDidLoad()
        overrideUserInterfaceStyle = .dark
        view.backgroundColor = BrowserPalette.background
        view.tintColor = BrowserPalette.accent
        tableView.accessibilityIdentifier = "forge-tabs-list"
        tableView.keyboardDismissMode = .onDrag
        search.delegate = self
        search.placeholder = text("Search tabs")
        search.accessibilityIdentifier = "forge-tabs-search"
        search.searchBarStyle = .minimal
        search.autocapitalizationType = .none
        search.autocorrectionType = .no
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: text("Done"), style: .done,
            target: self, action: #selector(done))
        navigationItem.rightBarButtonItem?.accessibilityIdentifier = "forge-tabs-done"
        modes.insertSegment(withTitle: text("Regular tabs"), at: 0, animated: false)
        modes.insertSegment(withTitle: text("Private tabs"), at: 1, animated: false)
        modes.accessibilityIdentifier = "forge-tabs-mode"
        modes.addTarget(self, action: #selector(modeChanged), for: .valueChanged)
        let header = UIView(frame: CGRect(x: 0, y: 0, width: 320, height: 116))
        modes.translatesAutoresizingMaskIntoConstraints = false
        search.translatesAutoresizingMaskIntoConstraints = false
        header.addSubview(modes)
        header.addSubview(search)
        NSLayoutConstraint.activate([
            modes.leadingAnchor.constraint(equalTo: header.leadingAnchor, constant: 16),
            modes.trailingAnchor.constraint(equalTo: header.trailingAnchor, constant: -16),
            modes.topAnchor.constraint(equalTo: header.topAnchor, constant: 8),
            modes.heightAnchor.constraint(equalToConstant: 44),
            search.leadingAnchor.constraint(equalTo: header.leadingAnchor, constant: 8),
            search.trailingAnchor.constraint(equalTo: header.trailingAnchor, constant: -8),
            search.topAnchor.constraint(equalTo: modes.bottomAnchor, constant: 4),
            search.bottomAnchor.constraint(equalTo: header.bottomAnchor, constant: -4)
        ])
        tableView.tableHeaderView = header
        empty.text = text("No matching tabs")
        empty.textColor = BrowserPalette.secondary
        empty.textAlignment = .center
        empty.numberOfLines = 0
        empty.accessibilityIdentifier = "forge-tabs-empty"
        NotificationCenter.default.addObserver(self, selector: #selector(cover),
            name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(uncover),
            name: UIApplication.didBecomeActiveNotification, object: nil)
        refresh()
    }

    func refresh() {
        guard isViewLoaded else { return }
        let state = snapshot()
        modes.selectedSegmentIndex = state.isPrivate ? 1 : 0
        title = String(format: text("Tabs (%ld)"), state.tabs.count)
        let newTab = UIBarButtonItem(title: text("New tab"), style: .plain, target: self, action: #selector(newTab))
        newTab.accessibilityIdentifier = "forge-tabs-add"
        newTab.isEnabled = state.tabs.count < BrowserSession.maximumTabs
        navigationItem.leftBarButtonItem = nil
        if state.isPrivate {
            let closeGroup = UIBarButtonItem(image: UIImage(systemName: "trash"), style: .plain,
                target: self, action: #selector(confirmClosePrivate))
            closeGroup.accessibilityLabel = text("Close all private tabs")
            closeGroup.accessibilityIdentifier = "forge-tabs-close-private"
            closeGroup.tintColor = .systemRed
            navigationItem.leftBarButtonItem = closeGroup
        }
        toolbarItems = [newTab]
        navigationController?.setToolbarHidden(false, animated: false)
        reloadMatches()
    }

    private func reloadMatches() {
        visibleTabs = snapshot().matching(search.text ?? "")
        tableView.backgroundView = visibleTabs.isEmpty ? empty : nil
        tableView.reloadData()
    }

    func searchBar(_ searchBar: UISearchBar, textDidChange searchText: String) { reloadMatches() }
    func searchBarSearchButtonClicked(_ searchBar: UISearchBar) { searchBar.resignFirstResponder() }
    private func finish(completion: (() -> Void)? = nil) {
        view.endEditing(true)
        if let presenter = navigationController?.presentingViewController {
            presenter.dismiss(animated: true, completion: completion)
        } else {
            dismiss(animated: true, completion: completion)
        }
    }

    @objc private func done() { finish() }
    @objc private func newTab() { finish(completion: addTab) }
    @objc private func modeChanged() {
        let privateMode = modes.selectedSegmentIndex == 1
        changeMode(privateMode)
        search.text = ""
        search.resignFirstResponder()
        refresh()
    }

    @objc private func confirmClosePrivate() {
        let alert = UIAlertController(title: text("Close all private tabs"),
            message: text("Close private tabs warning"), preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: text("Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: text("Close all private tabs"), style: .destructive) { [weak self] _ in
            self?.closePrivate()
            self?.search.text = ""
            self?.refresh()
        })
        alert.preferredAction = alert.actions.first
        present(alert, animated: true)
    }

    @objc private func cover() {
        guard snapshot().isPrivate, privacyCover == nil, let host = navigationController?.view else { return }
        let cover = UIView(frame: host.bounds)
        cover.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        cover.backgroundColor = BrowserPalette.background
        cover.accessibilityIdentifier = "forge-tabs-privacy-cover"
        host.addSubview(cover)
        privacyCover = cover
    }

    @objc private func uncover() { privacyCover?.removeFromSuperview(); privacyCover = nil }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int { visibleTabs.count }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let tab = visibleTabs[indexPath.row]
        let cell = UITableViewCell(style: .subtitle, reuseIdentifier: nil)
        let name = tab.title.isEmpty ? (tab.url == "about:blank" ? text("New tab") : tab.url) : tab.title
        cell.textLabel?.text = name
        cell.textLabel?.font = .preferredFont(forTextStyle: .headline)
        cell.textLabel?.adjustsFontForContentSizeCategory = true
        cell.textLabel?.numberOfLines = 0
        cell.detailTextLabel?.text = (tab.id == snapshot().selectedID ? text("Selected tab") + " · " : "") + tab.url
        cell.detailTextLabel?.font = .preferredFont(forTextStyle: .subheadline)
        cell.detailTextLabel?.adjustsFontForContentSizeCategory = true
        cell.detailTextLabel?.numberOfLines = 2
        cell.backgroundColor = BrowserPalette.surface
        cell.accessibilityIdentifier = "forge-tab-" + tab.id.uuidString
        let close = UIButton(type: .system)
        close.setImage(UIImage(systemName: "xmark"), for: .normal)
        close.tintColor = BrowserPalette.foreground
        close.frame = CGRect(x: 0, y: 0, width: 44, height: 44)
        close.accessibilityLabel = String(format: text("Close tab: %@"), name)
        close.accessibilityIdentifier = "forge-tab-close-" + tab.id.uuidString
        close.addAction(UIAction { [weak self] _ in
            self?.close(tab.id)
            self?.refresh()
        }, for: .touchUpInside)
        cell.accessoryView = close
        return cell
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        let id = visibleTabs[indexPath.row].id
        let select = select
        finish { select(id) }
    }
}
