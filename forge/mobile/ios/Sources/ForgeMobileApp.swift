/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import SwiftUI

@main
struct ForgeMobileApp: App {
    var body: some Scene {
        WindowGroup { BrowserScreen().preferredColorScheme(.dark) }
    }
}

struct BrowserScreen: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> BrowserController { BrowserController() }
    func updateUIViewController(_ controller: BrowserController, context: Context) {}
}
