/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import Foundation

enum NavigationPolicy {
    static func allows(_ url: URL) -> Bool {
        if url.absoluteString == "about:blank" { return true }
        return url.scheme?.lowercased() == "https" && !(url.host ?? "").isEmpty
            && url.user == nil && url.password == nil
    }

    static func input(_ text: String) -> URL? {
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !value.isEmpty else { return nil }
        if value.range(of: "^[A-Za-z][A-Za-z0-9+.-]*:", options: .regularExpression) != nil {
            guard let url = URL(string: value), allows(url) else { return nil }
            return url
        }
        if !value.contains(where: { $0.isWhitespace }), value.contains("."),
            let url = URL(string: "https://" + value), allows(url) { return url }
        var search = URLComponents(string: "https://duckduckgo.com/")!
        search.queryItems = [URLQueryItem(name: "q", value: value)]
        return search.url
    }
}
