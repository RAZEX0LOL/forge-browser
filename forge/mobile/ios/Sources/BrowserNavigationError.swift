/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import Foundation

enum BrowserNavigationError {
    // Never display localizedDescription: it can include URLs, credentials or paths.
    static func message(for error: Error) -> String? {
        let error = error as NSError
        guard error.domain == NSURLErrorDomain else { return "Page could not be loaded." }
        switch error.code {
        case NSURLErrorCancelled:
            return nil
        case NSURLErrorTimedOut:
            return "Connection timed out. Try again."
        case NSURLErrorNotConnectedToInternet, NSURLErrorNetworkConnectionLost,
             NSURLErrorCannotConnectToHost, NSURLErrorCannotFindHost, NSURLErrorDNSLookupFailed:
            return "Could not connect. Check your network and try again."
        case NSURLErrorSecureConnectionFailed, NSURLErrorServerCertificateHasBadDate,
             NSURLErrorServerCertificateUntrusted, NSURLErrorServerCertificateHasUnknownRoot,
             NSURLErrorServerCertificateNotYetValid, NSURLErrorClientCertificateRejected,
             NSURLErrorClientCertificateRequired:
            return "Secure connection failed. No certificate exception was added."
        default:
            return "Page could not be loaded."
        }
    }
}
