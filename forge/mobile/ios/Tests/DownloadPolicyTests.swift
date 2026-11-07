import XCTest
import UIKit
import WebKit
import Network
@testable import ForgeMobile

final class DownloadPolicyTests: XCTestCase {
    func testHTTPSAndSafeBoundedNames() {
        XCTAssertTrue(DownloadPolicy.allows(URL(string: "https://example.com/file")))
        for value in ["about:blank", "http://example.com", "file:///secret", "https://user:pass@example.com"] {
            XCTAssertFalse(DownloadPolicy.allows(URL(string: value)))
        }
        XCTAssertEqual(DownloadPolicy.filename("../../secret.txt"), "secret.txt")
        XCTAssertEqual(DownloadPolicy.filename("photo\u{202E}.exe\u{0000}"), "photo.exe")
        XCTAssertEqual(DownloadPolicy.filename("CON.txt"), "download")
        XCTAssertEqual(DownloadPolicy.filename("..."), "download")
        XCTAssertEqual(DownloadPolicy.filename("Пример.pdf"), "Пример.pdf")
        XCTAssertLessThanOrEqual(DownloadPolicy.filename(String(repeating: "я", count: 200)).utf8.count, 160)
    }

    @MainActor
    func testDownloadPanelStartsHiddenAndDoesNotOpenFiles() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let presenter = UIViewController()
        let downloads = BrowserDownloads(presenter: presenter, root: root)
        XCTAssertTrue(downloads.panel.isHidden)
        XCTAssertEqual(downloads.stage, .empty)
        XCTAssertNil(presenter.presentedViewController)
        let file = try DownloadStaging.destination(root: root, suggestedName: "active.txt")
        try Data("active".utf8).write(to: file)
        let another = BrowserDownloads(presenter: UIViewController(), root: root)
        XCTAssertTrue(another.panel.isHidden)
        XCTAssertEqual(try Data(contentsOf: file), Data("active".utf8), "Another window must not clear live staged files")
    }

    func testStagingProtectsFilesAndKeepsDuplicateNamesSeparate() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let first = try DownloadStaging.destination(root: root, suggestedName: "../../fixture.txt")
        let second = try DownloadStaging.destination(root: root, suggestedName: "fixture.txt")
        XCTAssertNotEqual(first, second)
        XCTAssertEqual(first.lastPathComponent, "fixture.txt")
        XCTAssertFalse(FileManager.default.fileExists(atPath: first.path))
        let directory = first.deletingLastPathComponent()
        XCTAssertEqual(try directory.resourceValues(forKeys: [.isExcludedFromBackupKey]).isExcludedFromBackup, true)
        try Data("first".utf8).write(to: first)
        try Data("second".utf8).write(to: second)
        XCTAssertEqual(try DownloadStaging.completedSize(first), 5)
        XCTAssertEqual(try Data(contentsOf: first), Data("first".utf8))
        XCTAssertEqual(try Data(contentsOf: second), Data("second".utf8))
    }

    func testStagingRejectsUnavailableStorageAndOversizedFiles() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        try Data().write(to: root)
        XCTAssertThrowsError(try DownloadStaging.destination(root: root, suggestedName: "fixture"))
        try FileManager.default.removeItem(at: root)
        let file = try DownloadStaging.destination(root: root, suggestedName: "fixture")
        FileManager.default.createFile(atPath: file.path, contents: nil)
        let handle = try FileHandle(forWritingTo: file)
        try handle.truncate(atOffset: UInt64(DownloadPolicy.maximumBytes + 1))
        try handle.close()
        XCTAssertThrowsError(try DownloadStaging.completedSize(file))
    }

    @MainActor
    func testNativeWebKitHTTPSDownloadRequiresConfirmationAndStagesFile() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let presenter = UIViewController()
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previous = scene.windows.first { $0.isKeyWindow }
        let window = UIWindow(windowScene: scene)
        window.frame = scene.coordinateSpace.bounds
        window.rootViewController = presenter
        window.makeKeyAndVisible()
        defer { window.isHidden = true; previous?.makeKeyAndVisible() }
        presenter.loadViewIfNeeded()
        let downloads = BrowserDownloads(presenter: presenter, root: root)
        let webConfiguration = WKWebViewConfiguration()
        webConfiguration.websiteDataStore = .nonPersistent()
        let networkConfiguration = URLSessionConfiguration.ephemeral
        if let raw = ProcessInfo.processInfo.environment["FORGE_TEST_HTTPS_PROXY_PORT"],
           let port = UInt16(raw), let endpointPort = NWEndpoint.Port(rawValue: port) {
            let proxy = ProxyConfiguration(httpCONNECTProxy: .hostPort(host: "127.0.0.1", port: endpointPort))
            webConfiguration.websiteDataStore.proxyConfigurations = [proxy]
            networkConfiguration.proxyConfigurations = [proxy]
        }
        let web = WKWebView(frame: .zero, configuration: webConfiguration)
        web.frame = presenter.view.bounds
        presenter.view.addSubview(web)
        XCTAssertNotNil(presenter.view.window)
        let url = URL(string: "https://razex.shop/forge/SHA256SUMS")!
        networkConfiguration.timeoutIntervalForRequest = 20
        networkConfiguration.timeoutIntervalForResource = 25
        let probe = URLSession(configuration: networkConfiguration)
        defer { probe.invalidateAndCancel() }
        var request = URLRequest(url: url)
        request.httpMethod = "HEAD"
        do {
            let (_, response) = try await probe.data(for: request)
            XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        } catch {
            let native = error as NSError
            XCTFail("HTTPS preflight failed: \(native.domain) \(native.code)")
            return
        }
        let attached = expectation(description: "Native WKDownload created")
        web.startDownload(using: URLRequest(url: url)) { download in
            downloads.attach(download)
            attached.fulfill()
        }
        await fulfillment(of: [attached], timeout: 30)
        for _ in 0..<300 where downloads.stage != .confirming && downloads.stage != .failed {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        guard downloads.stage == .confirming else {
            XCTFail(downloads.failureReason ?? "Download did not reach confirmation")
            return
        }
        XCTAssertNotNil(presenter.presentedViewController as? UIAlertController)
        downloads.start()
        for _ in 0..<300 where downloads.stage != .ready && downloads.stage != .failed {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        guard downloads.stage == .ready else {
            XCTFail(downloads.failureReason ?? "Download did not finish")
            return
        }
        let directories = try FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)
        let file = try XCTUnwrap(directories.first).appendingPathComponent("SHA256SUMS")
        let data = try Data(contentsOf: file)
        XCTAssertEqual(data.count, 1266)
        XCTAssertTrue(String(decoding: data, as: UTF8.self).hasPrefix("c90f8d5e32e5ace6887a2a464c2f5078f7b7cc7cc1b485fad231d0f3d611d776"))
        downloads.cancel()
        XCTAssertFalse(FileManager.default.fileExists(atPath: file.path))
    }
}
