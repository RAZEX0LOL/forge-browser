/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import WebKit

@MainActor
enum BrowserSiteData {
    static func clear(_ stores: [WKWebsiteDataStore], completion: @escaping (Bool) -> Void) {
        guard let store = stores.first else { completion(true); return }
        let types = WKWebsiteDataStore.allWebsiteDataTypes()
        store.removeData(ofTypes: types, modifiedSince: .distantPast) {
            // WebKit's removal callback has no error argument. Check both records
            // and session cookies before reporting success; never clear app files.
            store.fetchDataRecords(ofTypes: types) { records in
                store.httpCookieStore.getAllCookies { cookies in
                    guard records.isEmpty, cookies.isEmpty else { completion(false); return }
                    clear(Array(stores.dropFirst()), completion: completion)
                }
            }
        }
    }
}
