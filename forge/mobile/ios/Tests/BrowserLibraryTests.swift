import XCTest
@testable import ForgeMobile

@MainActor
final class BrowserLibraryTests: XCTestCase {
    private func directory() throws -> URL {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent("forge-library-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: directory) }
        return directory
    }

    func testVisitDeduplicationPreservesIDAndMovesRecentFirst() throws {
        var library = BrowserLibrary()
        library.recordVisit(url: "https://one.invalid", title: "One", isPrivate: false, now: 1)
        let id = library.history[0].id
        library.recordVisit(url: "https://two.invalid", title: "Two", isPrivate: false, now: 2)
        library.recordVisit(url: "https://one.invalid", title: "Updated", isPrivate: false, now: 3)
        XCTAssertEqual(library.history.count, 2)
        XCTAssertEqual(library.history[0].id, id)
        XCTAssertEqual(library.history[0].title, "Updated")
        try library.validate()
    }

    func testPrivateOperationsDoNotCreateAFileEvenWithUnavailableStore() throws {
        let directory = try self.directory()
        let store = BrowserLibraryStore(directory: directory)
        XCTAssertFalse(try store.recordVisit(url: "https://private.invalid", title: "Secret", isPrivate: true))
        XCTAssertFalse(try store.addBookmark(url: "https://private.invalid", title: "Secret", isPrivate: true))
        XCTAssertFalse(FileManager.default.fileExists(atPath: store.fileURL.path))
        let corrupt = Data("corrupt fixture".utf8)
        try corrupt.write(to: store.fileURL)
        let unavailable = BrowserLibraryStore(directory: directory)
        XCTAssertFalse(unavailable.isAvailable)
        XCTAssertFalse(try unavailable.recordVisit(url: "https://private.invalid", title: "Secret", isPrivate: true))
        XCTAssertEqual(try Data(contentsOf: store.fileURL), corrupt)
    }

    func testBoundedHistoryAndBookmarksHaveIndependentDeletion() throws {
        var library = BrowserLibrary()
        for i in 0..<(BrowserLibrary.maximumHistory + 5) {
            XCTAssertTrue(library.recordVisit(url: "https://history.invalid/\(i)", title: "Visit", isPrivate: false, now: Int64(i + 1)))
        }
        XCTAssertEqual(library.history.count, BrowserLibrary.maximumHistory)
        for i in 0..<BrowserLibrary.maximumBookmarks {
            XCTAssertTrue(library.addBookmark(url: "https://bookmark.invalid/\(i)", title: "Bookmark", isPrivate: false, now: Int64(i + 1)))
        }
        XCTAssertFalse(library.addBookmark(url: "https://bookmark.invalid/overflow", title: "Overflow", isPrivate: false, now: 999))
        XCTAssertTrue(library.addBookmark(url: "https://bookmark.invalid/0", title: "Updated", isPrivate: false, now: 1000))
        XCTAssertEqual(library.bookmarks.count, BrowserLibrary.maximumBookmarks)
        library.clearHistory()
        XCTAssertTrue(library.history.isEmpty)
        XCTAssertEqual(library.bookmarks.count, BrowserLibrary.maximumBookmarks)
        try library.validate()
    }

    func testAtomicStoreRoundTripAndExplicitHistoryClearPreserveBookmarks() throws {
        let directory = try self.directory()
        let store = BrowserLibraryStore(directory: directory)
        XCTAssertTrue(try store.addBookmark(url: "https://example.invalid", title: "Bookmark", isPrivate: false))
        XCTAssertTrue(try store.recordVisit(url: "https://example.invalid", title: "Visit", isPrivate: false))
        let reopened = BrowserLibraryStore(directory: directory)
        XCTAssertTrue(reopened.isAvailable)
        XCTAssertEqual(reopened.snapshot, store.snapshot)
        try reopened.clearHistory()
        let cleared = BrowserLibraryStore(directory: directory)
        XCTAssertTrue(cleared.snapshot.history.isEmpty)
        XCTAssertEqual(cleared.snapshot.bookmarks.count, 1)
        XCTAssertEqual(try directory.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup, true)
        try cleared.remove(try XCTUnwrap(cleared.snapshot.bookmarks.first).id, bookmarks: true)
        XCTAssertTrue(BrowserLibraryStore(directory: directory).snapshot.bookmarks.isEmpty)
    }

    func testCorruptFutureAndDuplicateLibraryFilesStayUntouched() throws {
        let directory = try self.directory()
        let file = directory.appendingPathComponent("library-v1.json")
        let id = UUID().uuidString
        let entry = "{\"id\":\"\(id)\",\"url\":\"https://example.invalid\",\"title\":\"Fixture\",\"updatedAt\":1}"
        for fixture in ["corrupt", "{\"schemaVersion\":2,\"history\":[],\"bookmarks\":[]}",
                        "{\"schemaVersion\":1,\"history\":[\(entry),\(entry)],\"bookmarks\":[]}"] {
            let bytes = Data(fixture.utf8); try bytes.write(to: file)
            let store = BrowserLibraryStore(directory: directory)
            XCTAssertFalse(store.isAvailable)
            XCTAssertThrowsError(try store.addBookmark(url: "https://new.invalid", title: "New", isPrivate: false))
            XCTAssertThrowsError(try store.clearHistory())
            XCTAssertEqual(try Data(contentsOf: file), bytes)
        }
    }

    func testHostileURLsAreRejectedAndTitlesBounded() throws {
        var library = BrowserLibrary()
        for value in ["about:blank", "file:///private", "javascript:alert(1)", "https://user:secret@example.invalid"] {
            XCTAssertFalse(library.recordVisit(url: value, title: "Bad", isPrivate: false, now: 1))
            XCTAssertFalse(library.addBookmark(url: value, title: "Bad", isPrivate: false, now: 1))
        }
        library.addBookmark(url: "https://example.invalid", title: String(repeating: "😀", count: 200), isPrivate: false, now: 1)
        XCTAssertEqual(library.bookmarks[0].title.count, 160)
        try library.validate()
    }
}
