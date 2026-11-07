/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import Foundation

struct BrowserLibraryEntry: Codable, Equatable, Identifiable {
    let id: UUID
    let url: String
    let title: String
    let updatedAt: Int64
}

struct BrowserLibrary: Codable, Equatable {
    static let maximumHistory = 500
    static let maximumBookmarks = 200
    static let maximumBytes = 8 * 1024 * 1024
    let schemaVersion: Int
    private(set) var bookmarks: [BrowserLibraryEntry]
    private(set) var history: [BrowserLibraryEntry]

    init() { schemaVersion = 1; bookmarks = []; history = [] }

    func validate() throws {
        let entries = bookmarks + history
        guard schemaVersion == 1, bookmarks.count <= Self.maximumBookmarks, history.count <= Self.maximumHistory,
              Set(entries.map(\.id)).count == entries.count,
              Set(bookmarks.map(\.url)).count == bookmarks.count,
              Set(history.map(\.url)).count == history.count,
              entries.allSatisfy({ BrowserLinkActions.shareURL($0.url) != nil && $0.title.utf8.count <= 1024 && $0.updatedAt > 0 })
        else { throw LibraryError.invalidLibrary }
    }

    @discardableResult mutating func recordVisit(url: String, title: String, isPrivate: Bool, now: Int64) -> Bool {
        guard !isPrivate, now > 0, BrowserLinkActions.shareURL(url) != nil else { return false }
        let old = history.first { $0.url == url }
        history.removeAll { $0.url == url }
        history.insert(BrowserLibraryEntry(id: old?.id ?? UUID(), url: url, title: String(title.prefix(160)), updatedAt: now), at: 0)
        history = Array(history.prefix(Self.maximumHistory))
        return true
    }

    @discardableResult mutating func addBookmark(url: String, title: String, isPrivate: Bool, now: Int64) -> Bool {
        guard !isPrivate, now > 0, BrowserLinkActions.shareURL(url) != nil else { return false }
        let old = bookmarks.first { $0.url == url }
        guard old != nil || bookmarks.count < Self.maximumBookmarks else { return false }
        bookmarks.removeAll { $0.url == url }
        bookmarks.insert(BrowserLibraryEntry(id: old?.id ?? UUID(), url: url, title: String(title.prefix(160)), updatedAt: now), at: 0)
        return true
    }

    mutating func removeBookmark(_ id: UUID) { bookmarks.removeAll { $0.id == id } }
    mutating func removeHistory(_ id: UUID) { history.removeAll { $0.id == id } }
    mutating func clearHistory() { history.removeAll() }
}

enum LibraryError: Error { case unavailable, invalidLibrary, oversizedLibrary }

@MainActor
final class BrowserLibraryStore {
    static let shared = BrowserLibraryStore()
    let fileURL: URL
    private(set) var snapshot = BrowserLibrary()
    private(set) var isAvailable = true

    init(directory: URL? = nil) {
        let root = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("ForgeBrowser", isDirectory: true)
        fileURL = root.appendingPathComponent("library-v1.json")
        guard FileManager.default.fileExists(atPath: fileURL.path) else { return }
        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
            guard ((attributes[.size] as? NSNumber)?.intValue ?? Int.max) <= BrowserLibrary.maximumBytes
            else { throw LibraryError.oversizedLibrary }
            let library = try JSONDecoder().decode(BrowserLibrary.self, from: Data(contentsOf: fileURL))
            try library.validate()
            snapshot = library
        } catch { isAvailable = false }
    }

    private func save(_ library: BrowserLibrary) throws {
        guard isAvailable else { throw LibraryError.unavailable }
        do {
            try library.validate()
            let data = try JSONEncoder().encode(library)
            guard data.count <= BrowserLibrary.maximumBytes else { throw LibraryError.oversizedLibrary }
            var directory = fileURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            var values = URLResourceValues(); values.isExcludedFromBackup = true
            try directory.setResourceValues(values)
            try data.write(to: fileURL, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
            snapshot = library
        } catch { isAvailable = false; throw error }
    }

    @discardableResult func recordVisit(url: String, title: String, isPrivate: Bool) throws -> Bool {
        guard !isPrivate else { return false }
        guard isAvailable else { throw LibraryError.unavailable }
        var next = snapshot
        guard next.recordVisit(url: url, title: title, isPrivate: false, now: Self.now()) else { return false }
        try save(next); return true
    }

    @discardableResult func addBookmark(url: String, title: String, isPrivate: Bool) throws -> Bool {
        guard !isPrivate else { return false }
        guard isAvailable else { throw LibraryError.unavailable }
        var next = snapshot
        guard next.addBookmark(url: url, title: title, isPrivate: false, now: Self.now()) else { return false }
        try save(next); return true
    }

    func remove(_ id: UUID, bookmarks: Bool) throws {
        var next = snapshot
        if bookmarks { next.removeBookmark(id) } else { next.removeHistory(id) }
        try save(next)
    }

    func clearHistory() throws {
        var next = snapshot; next.clearHistory(); try save(next)
    }

    private static func now() -> Int64 { Int64(Date().timeIntervalSince1970 * 1000) }
}
