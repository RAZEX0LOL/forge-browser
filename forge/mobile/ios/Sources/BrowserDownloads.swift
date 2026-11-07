/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import UIKit
import WebKit

enum DownloadPolicy {
    static let maximumBytes: Int64 = 256 * 1024 * 1024

    static func allows(_ url: URL?) -> Bool {
        guard let url = url else { return false }
        return url.scheme?.lowercased() == "https" && NavigationPolicy.allows(url)
    }

    static func filename(_ suggestion: String) -> String {
        var result = ""
        for scalar in suggestion.unicodeScalars {
            if CharacterSet.letters.contains(scalar) || CharacterSet.decimalDigits.contains(scalar)
                || " ._-()".unicodeScalars.contains(scalar) {
                if result.utf8.count + scalar.utf8.count <= 160 { result.unicodeScalars.append(scalar) }
            }
        }
        result = result.trimmingCharacters(in: CharacterSet(charactersIn: " ."))
        let stem = result.split(separator: ".").first.map(String.init)?.uppercased() ?? ""
        if result.isEmpty || stem.range(of: "^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$", options: .regularExpression) != nil {
            return "download"
        }
        return result
    }
}

enum DownloadStaging {
    static func destination(root: URL, suggestedName: String) throws -> URL {
        let directory = root.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true,
            attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication])
        do {
            var protected = directory
            var values = URLResourceValues()
            values.isExcludedFromBackup = true
            try protected.setResourceValues(values)
            return directory.appendingPathComponent(DownloadPolicy.filename(suggestedName))
        } catch {
            try? FileManager.default.removeItem(at: directory)
            throw error
        }
    }

    static func completedSize(_ file: URL) throws -> Int64 {
        let attributes = try FileManager.default.attributesOfItem(atPath: file.path)
        guard attributes[.type] as? FileAttributeType == .typeRegular,
              let size = (attributes[.size] as? NSNumber)?.int64Value,
              size <= DownloadPolicy.maximumBytes else { throw CocoaError(.fileReadCorruptFile) }
        return size
    }
}

@MainActor
final class BrowserDownloads: NSObject, WKDownloadDelegate, UIDocumentPickerDelegate {
    private static var cleanedRoots = Set<String>()
    enum Stage { case empty, confirming, receiving, ready, exporting, saved, cancelled, failed }
    private(set) var stage = Stage.empty
    private(set) var failureReason: String?
    let panel = UIStackView()
    private let label = UILabel()
    private let progress = UIProgressView(progressViewStyle: .default)
    private let saveButton = UIButton(type: .system)
    private let cancelButton = UIButton(type: .system)
    private weak var presenter: UIViewController?
    private var active: WKDownload?
    private var pendingDestination: ((URL?) -> Void)?
    private var observations: [NSKeyValueObservation] = []
    private var directory: URL?
    private var file: URL?
    private var name = "download"
    private var received: Int64 = 0
    private var redirects = 0
    private let root: URL
    private var confirmation: UIAlertController?
    private var notification: NSObjectProtocol?

    init(presenter: UIViewController, root: URL? = nil) {
        self.presenter = presenter
        self.root = root ?? FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("ForgeDownloads", isDirectory: true)
        super.init()
        if Self.cleanedRoots.insert(self.root.path).inserted,
           let old = try? FileManager.default.contentsOfDirectory(at: self.root, includingPropertiesForKeys: nil) {
            for url in old where UUID(uuidString: url.lastPathComponent) != nil { try? FileManager.default.removeItem(at: url) }
        }
        panel.axis = .vertical
        panel.spacing = 4
        panel.backgroundColor = BrowserPalette.field
        panel.layer.cornerRadius = 16
        panel.isLayoutMarginsRelativeArrangement = true
        panel.directionalLayoutMargins = NSDirectionalEdgeInsets(top: 12, leading: 14, bottom: 8, trailing: 14)
        panel.accessibilityIdentifier = "forge-download-panel"
        label.numberOfLines = 0
        label.font = .preferredFont(forTextStyle: .caption1)
        label.textColor = BrowserPalette.foreground
        label.adjustsFontForContentSizeCategory = true
        label.accessibilityIdentifier = "forge-download-status"
        panel.addArrangedSubview(label)
        panel.addArrangedSubview(progress)
        let actions = UIStackView(arrangedSubviews: [saveButton, cancelButton])
        actions.distribution = .fillEqually
        for button in [saveButton, cancelButton] {
            let height = button.heightAnchor.constraint(greaterThanOrEqualToConstant: 48)
            height.priority = UILayoutPriority(999)
            height.isActive = true
        }
        saveButton.addAction(UIAction { [weak self] _ in self?.exportFile() }, for: .touchUpInside)
        cancelButton.addAction(UIAction { [weak self] _ in self?.cancel() }, for: .touchUpInside)
        panel.addArrangedSubview(actions)
        notification = NotificationCenter.default.addObserver(forName: UIApplication.didEnterBackgroundNotification,
            object: nil, queue: .main) { [weak self] _ in
                MainActor.assumeIsolated {
                    if self?.stage == .receiving || self?.stage == .confirming { self?.cancel() }
                }
            }
        refresh()
    }

    deinit {
        if let notification = notification { NotificationCenter.default.removeObserver(notification) }
        let abandoned = directory
        let previous = active
        let completion = pendingDestination
        MainActor.assumeIsolated {
            completion?(nil)
            if let previous = previous {
                previous.cancel { _ in if let abandoned = abandoned { try? FileManager.default.removeItem(at: abandoned) } }
            } else if let abandoned = abandoned { try? FileManager.default.removeItem(at: abandoned) }
        }
    }

    private func text(_ key: String) -> String { NSLocalizedString(key, comment: "Forge downloads") }

    private func refresh() {
        panel.isHidden = stage == .empty
        let key: String
        switch stage {
        case .confirming: key = "Download file? Maximum 256 MiB."
        case .receiving: key = "Downloading…"
        case .ready: key = "Download ready. Choose Save to Files."
        case .exporting: key = "Choose where to save the file."
        case .saved: key = "File saved. It was not opened."
        case .cancelled: key = "Download cancelled."
        default: key = "Download failed. Check the network and available space, then retry from the page."
        }
        label.text = String(format: text("%@\n%@\n%lld bytes"), name, text(key), received)
        progress.isHidden = stage != .receiving
        let total = active?.progress.totalUnitCount ?? 0
        progress.progress = total > 0 ? min(1, Float(received) / Float(total)) : 0
        saveButton.setTitle(text("Save to Files"), for: .normal)
        saveButton.isHidden = stage != .ready
        cancelButton.setTitle(text(stage == .receiving || stage == .confirming ? "Cancel" : "Clear download"), for: .normal)
        cancelButton.isEnabled = stage != .exporting
    }

    func attach(_ download: WKDownload) {
        guard active == nil, stage != .ready, stage != .exporting,
              DownloadPolicy.allows(download.originalRequest?.url) else {
            download.cancel(nil)
            return
        }
        active = download
        failureReason = nil
        redirects = 0
        received = 0
        download.delegate = self
        observations = [download.progress.observe(\.completedUnitCount, options: [.new]) { [weak self] _, _ in
            DispatchQueue.main.async { self?.updateProgress() }
        }]
    }

    private func updateProgress() {
        guard let active = active, stage == .receiving else { return }
        received = active.progress.completedUnitCount
        if received > DownloadPolicy.maximumBytes { fail("size-limit"); return }
        refresh()
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String,
                  completionHandler: @escaping (URL?) -> Void) {
        guard download === active, DownloadPolicy.allows(response.url),
              let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              http.statusCode != 204, http.statusCode != 206,
              response.expectedContentLength <= DownloadPolicy.maximumBytes,
              let presenter = presenter, presenter.viewIfLoaded?.window != nil,
              presenter.presentedViewController == nil else {
            completionHandler(nil)
            if download === active {
                let httpStatus = (response as? HTTPURLResponse)?.statusCode ?? 0
                fail("destination-rejected: status=\(httpStatus), bytes=\(response.expectedContentLength), visible=\(presenter?.viewIfLoaded?.window != nil), modal=\(presenter?.presentedViewController != nil)")
            }
            return
        }
        name = DownloadPolicy.filename(suggestedFilename)
        stage = .confirming
        pendingDestination = completionHandler
        refresh()
        let alert = UIAlertController(title: text("Download file? Maximum 256 MiB."), message: name, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: text("Download"), style: .default) { [weak self] _ in self?.start() })
        alert.addAction(UIAlertAction(title: text("Cancel"), style: .cancel) { [weak self] _ in self?.cancel() })
        confirmation = alert
        presenter.present(alert, animated: true)
    }

    func start() {
        guard stage == .confirming, let completion = pendingDestination else { return }
        pendingDestination = nil
        confirmation?.dismiss(animated: false)
        confirmation = nil
        do {
            let file = try DownloadStaging.destination(root: root, suggestedName: name)
            self.directory = file.deletingLastPathComponent()
            self.file = file
            stage = .receiving
            refresh()
            completion(file)
        } catch {
            completion(nil)
            fail("staging-write-failed")
        }
    }

    func download(_ download: WKDownload, willPerformHTTPRedirection response: HTTPURLResponse,
                  newRequest request: URLRequest, decisionHandler: @escaping (WKDownload.RedirectPolicy) -> Void) {
        redirects += 1
        let allowed = download === active && redirects <= 10 && DownloadPolicy.allows(request.url)
        decisionHandler(allowed ? .allow : .cancel)
        if !allowed && download === active { fail("unsafe-redirect") }
    }

    func downloadDidFinish(_ download: WKDownload) {
        guard download === active, let file = file else { return }
        guard let bytes = try? DownloadStaging.completedSize(file) else { fail("invalid-completed-file"); return }
        received = bytes
        active = nil
        observations = []
        stage = .ready
        refresh()
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        if download === active {
            let native = error as NSError
            fail("native-error: \(native.domain) \(native.code)")
        }
    }

    private func cleanup(_ directory: URL?) { if let directory = directory { try? FileManager.default.removeItem(at: directory) } }

    private func stop(_ nextStage: Stage) {
        let completion = pendingDestination
        pendingDestination = nil
        let previous = active
        active = nil
        observations = []
        let abandoned = directory
        directory = nil
        file = nil
        stage = nextStage
        completion?(nil)
        confirmation?.dismiss(animated: false)
        confirmation = nil
        if let previous = previous {
            previous.cancel { _ in if let abandoned = abandoned { try? FileManager.default.removeItem(at: abandoned) } }
        }
        else { cleanup(abandoned) }
        refresh()
    }

    func cancel() {
        guard stage != .exporting else { return }
        stop(stage == .saved || stage == .failed || stage == .cancelled ? .empty : .cancelled)
    }

    private func fail(_ reason: String) { failureReason = reason; stop(.failed) }

    private func exportFile() {
        guard stage == .ready, let file = file, let presenter = presenter,
              presenter.presentedViewController == nil else { return }
        let picker = UIDocumentPickerViewController(forExporting: [file], asCopy: true)
        picker.delegate = self
        stage = .exporting
        refresh()
        presenter.present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard stage == .exporting else { return }
        if urls.isEmpty { stage = .ready; refresh(); return }
        cleanup(directory)
        directory = nil
        file = nil
        stage = .saved
        refresh()
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        guard stage == .exporting else { return }
        stage = .ready
        refresh()
    }
}
