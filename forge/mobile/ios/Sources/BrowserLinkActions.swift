/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import Foundation

enum BrowserLinkActions {
    static func shareURL(_ value: String) -> URL? {
        guard value.utf8.count <= 8192, let url = URL(string: value),
              url.scheme?.lowercased() == "https", NavigationPolicy.allows(url) else { return nil }
        return url
    }
}
