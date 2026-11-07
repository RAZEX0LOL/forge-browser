/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import Foundation

struct BrowserTab: Codable, Equatable, Identifiable {
    let id: UUID
    var url: String
    var title: String

    init(id: UUID = UUID(), url: String = "about:blank", title: String = "") {
        self.id = id
        self.url = url
        self.title = title
    }
}

struct BrowserSession: Codable, Equatable {
    static let maximumTabs = 32
    let schemaVersion: Int
    private(set) var tabs: [BrowserTab]
    private(set) var selectedID: UUID

    init() {
        let first = BrowserTab()
        schemaVersion = 1
        tabs = [first]
        selectedID = first.id
    }

    var selectedTab: BrowserTab { tabs.first { $0.id == selectedID }! }

    func validate() throws {
        guard schemaVersion == 1, !tabs.isEmpty, tabs.count <= Self.maximumTabs,
              Set(tabs.map(\.id)).count == tabs.count,
              tabs.contains(where: { $0.id == selectedID }),
              tabs.allSatisfy({ tab in
                  tab.url.utf8.count <= 8192 && tab.title.utf8.count <= 1024 &&
                      URL(string: tab.url).map(NavigationPolicy.allows) == true
              }) else { throw SessionError.invalidSession }
    }

    @discardableResult mutating func addTab() -> UUID? {
        guard tabs.count < Self.maximumTabs else { return nil }
        let tab = BrowserTab()
        tabs.append(tab)
        selectedID = tab.id
        return tab.id
    }

    @discardableResult mutating func select(_ id: UUID) -> Bool {
        guard tabs.contains(where: { $0.id == id }) else { return false }
        selectedID = id
        return true
    }

    mutating func close(_ id: UUID) {
        guard let index = tabs.firstIndex(where: { $0.id == id }) else { return }
        tabs.remove(at: index)
        if tabs.isEmpty { tabs = [BrowserTab()] }
        if selectedID == id { selectedID = tabs[min(index, tabs.count - 1)].id }
    }

    @discardableResult mutating func update(_ id: UUID, url: String? = nil, title: String? = nil) -> Bool {
        guard let index = tabs.firstIndex(where: { $0.id == id }) else { return false }
        if let url = url {
            guard url.utf8.count <= 8192, URL(string: url).map(NavigationPolicy.allows) == true else { return false }
            tabs[index].url = url
        }
        if let title = title { tabs[index].title = String(title.prefix(160)) }
        return true
    }
}

enum SessionError: Error { case invalidSession, oversizedSession }

final class BrowserSessionStore {
    static let maximumBytes = 512 * 1024
    let fileURL: URL

    init(directory: URL? = nil) {
        let root = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("ForgeBrowser", isDirectory: true)
        fileURL = root.appendingPathComponent("session-v1.json")
    }

    func load() throws -> BrowserSession? {
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return nil }
        let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
        guard ((attributes[.size] as? NSNumber)?.intValue ?? Int.max) <= Self.maximumBytes else {
            throw SessionError.oversizedSession
        }
        let session = try JSONDecoder().decode(BrowserSession.self, from: Data(contentsOf: fileURL))
        try session.validate()
        return session
    }

    func save(_ session: BrowserSession) throws {
        try session.validate()
        let data = try JSONEncoder().encode(session)
        guard data.count <= Self.maximumBytes else { throw SessionError.oversizedSession }
        var directory = fileURL.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try directory.setResourceValues(values)
        try data.write(to: fileURL, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
    }
}
