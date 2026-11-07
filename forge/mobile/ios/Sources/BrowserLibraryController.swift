/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import UIKit

final class BrowserLibraryController: UITableViewController, UISearchBarDelegate {
    private let store: BrowserLibraryStore
    private let open: (String) -> Void
    private let privateMode: Bool
    private var showingBookmarks: Bool
    private let modes = UISegmentedControl()
    private let search = UISearchBar()
    private let empty = UILabel()
    private var entries: [BrowserLibraryEntry] = []
    private var cover: UIView?

    init(store: BrowserLibraryStore, bookmarks: Bool, privateMode: Bool, open: @escaping (String) -> Void) {
        self.store = store; self.showingBookmarks = bookmarks; self.privateMode = privateMode; self.open = open
        super.init(style: .insetGrouped)
    }
    required init?(coder: NSCoder) { return nil }
    deinit { NotificationCenter.default.removeObserver(self) }
    private func text(_ key: String) -> String { NSLocalizedString(key, comment: "Forge library") }

    override func viewDidLoad() {
        super.viewDidLoad()
        overrideUserInterfaceStyle = .dark
        tableView.backgroundColor = BrowserPalette.background
        tableView.accessibilityIdentifier = "forge-library-list"
        tableView.keyboardDismissMode = .onDrag
        navigationItem.rightBarButtonItem = UIBarButtonItem(title: text("Done"), style: .done, target: self, action: #selector(done))
        navigationItem.rightBarButtonItem?.accessibilityIdentifier = "forge-library-done"
        modes.insertSegment(withTitle: text("Bookmarks"), at: 0, animated: false)
        modes.insertSegment(withTitle: text("History"), at: 1, animated: false)
        modes.addTarget(self, action: #selector(modeChanged), for: .valueChanged)
        modes.accessibilityIdentifier = "forge-library-mode"
        search.delegate = self
        search.placeholder = text("Search library")
        search.accessibilityIdentifier = "forge-library-search"
        search.searchBarStyle = .minimal
        search.autocapitalizationType = .none
        search.autocorrectionType = .no
        let header = UIView(frame: CGRect(x: 0, y: 0, width: 320, height: 116))
        for control in [modes, search] { control.translatesAutoresizingMaskIntoConstraints = false; header.addSubview(control) }
        NSLayoutConstraint.activate([
            modes.topAnchor.constraint(equalTo: header.topAnchor, constant: 8),
            modes.leadingAnchor.constraint(equalTo: header.leadingAnchor, constant: 16),
            modes.trailingAnchor.constraint(equalTo: header.trailingAnchor, constant: -16),
            modes.heightAnchor.constraint(equalToConstant: 44),
            search.topAnchor.constraint(equalTo: modes.bottomAnchor, constant: 4),
            search.leadingAnchor.constraint(equalTo: header.leadingAnchor, constant: 8),
            search.trailingAnchor.constraint(equalTo: header.trailingAnchor, constant: -8),
            search.bottomAnchor.constraint(equalTo: header.bottomAnchor, constant: -4)
        ])
        tableView.tableHeaderView = header
        empty.textAlignment = .center; empty.numberOfLines = 0; empty.textColor = BrowserPalette.secondary
        empty.accessibilityIdentifier = "forge-library-empty"
        NotificationCenter.default.addObserver(self, selector: #selector(hidePrivateContent), name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(showPrivateContent), name: UIApplication.didBecomeActiveNotification, object: nil)
        refresh()
    }

    func refresh() {
        guard isViewLoaded else { return }
        modes.selectedSegmentIndex = showingBookmarks ? 0 : 1
        title = text(showingBookmarks ? "Bookmarks" : "History")
        let query = (search.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let snapshot = store.snapshot
        entries = (showingBookmarks ? snapshot.bookmarks : snapshot.history).filter {
            query.isEmpty || $0.title.localizedCaseInsensitiveContains(query) || $0.url.localizedCaseInsensitiveContains(query)
        }
        empty.text = text(store.isAvailable ? "No saved entries" : "Library storage is unavailable. Existing data was not changed.")
        tableView.backgroundView = entries.isEmpty ? empty : nil
        if !store.isAvailable && !entries.isEmpty {
            let warning = UILabel(frame: CGRect(x: 0, y: 0, width: 320, height: 100))
            warning.text = text("Library storage is unavailable. Existing data was not changed.")
            warning.numberOfLines = 0; warning.textColor = .systemOrange; warning.textAlignment = .center
            warning.accessibilityIdentifier = "forge-library-warning"
            tableView.tableFooterView = warning
        } else { tableView.tableFooterView = nil }
        let clear = UIBarButtonItem(image: UIImage(systemName: "trash"), style: .plain, target: self, action: #selector(confirmClearHistory))
        clear.accessibilityLabel = text("Clear history")
        clear.accessibilityIdentifier = "forge-library-clear-history"
        clear.tintColor = .systemRed
        clear.isEnabled = store.isAvailable && !snapshot.history.isEmpty
        navigationItem.leftBarButtonItem = showingBookmarks ? nil : clear
        tableView.reloadData()
    }

    func searchBar(_ searchBar: UISearchBar, textDidChange searchText: String) { refresh() }
    func searchBarSearchButtonClicked(_ searchBar: UISearchBar) { searchBar.resignFirstResponder() }
    @objc private func modeChanged() {
        showingBookmarks = modes.selectedSegmentIndex == 0
        search.text = ""; search.resignFirstResponder(); refresh()
    }
    @objc private func done() { navigationController?.presentingViewController?.dismiss(animated: true) }

    func makeClearHistoryConfirmation() -> UIAlertController {
        let alert = UIAlertController(title: text("Clear history"), message: text("Clear history warning"), preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: text("Cancel"), style: .cancel))
        alert.addAction(UIAlertAction(title: text("Clear history"), style: .destructive) { [weak self] _ in
            guard let self = self else { return }
            do { try self.store.clearHistory() } catch { /* Visible persistent unavailable state below. */ }
            self.refresh()
        })
        alert.preferredAction = alert.actions.first
        return alert
    }
    @objc private func confirmClearHistory() { present(makeClearHistoryConfirmation(), animated: true) }

    @objc private func hidePrivateContent() {
        guard privateMode, cover == nil, let host = navigationController?.view else { return }
        let view = UIView(frame: host.bounds)
        view.backgroundColor = BrowserPalette.background
        view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.accessibilityIdentifier = "forge-library-privacy-cover"
        host.addSubview(view); cover = view
    }
    @objc private func showPrivateContent() { cover?.removeFromSuperview(); cover = nil }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int { entries.count }
    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let entry = entries[indexPath.row]
        let cell = UITableViewCell(style: .subtitle, reuseIdentifier: nil)
        cell.textLabel?.text = entry.title.isEmpty ? entry.url : entry.title
        cell.textLabel?.font = .preferredFont(forTextStyle: .headline)
        cell.textLabel?.adjustsFontForContentSizeCategory = true
        cell.textLabel?.numberOfLines = 2
        cell.detailTextLabel?.text = entry.url
        cell.detailTextLabel?.font = .preferredFont(forTextStyle: .subheadline)
        cell.detailTextLabel?.adjustsFontForContentSizeCategory = true
        cell.detailTextLabel?.numberOfLines = 2
        cell.backgroundColor = BrowserPalette.surface
        cell.accessoryType = .disclosureIndicator
        cell.accessibilityIdentifier = "forge-library-entry-" + entry.id.uuidString
        return cell
    }
    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        let url = entries[indexPath.row].url, open = open
        view.endEditing(true)
        navigationController?.presentingViewController?.dismiss(animated: true) { open(url) }
    }
    override func tableView(_ tableView: UITableView, trailingSwipeActionsConfigurationForRowAt indexPath: IndexPath) -> UISwipeActionsConfiguration? {
        guard store.isAvailable else { return nil }
        let id = entries[indexPath.row].id, bookmarks = showingBookmarks
        let delete = UIContextualAction(style: .destructive, title: text("Delete entry")) { [weak self] _, _, done in
            guard let self = self else { done(false); return }
            do { try self.store.remove(id, bookmarks: bookmarks); done(true) }
            catch { done(false) }
            self.refresh()
        }
        return UISwipeActionsConfiguration(actions: [delete])
    }
}
