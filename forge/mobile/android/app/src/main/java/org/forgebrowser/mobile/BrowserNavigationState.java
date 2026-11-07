/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import org.mozilla.geckoview.WebRequestError;

final class BrowserNavigationState {
    enum Phase { IDLE, LOADING, READY, FAILED, STOPPED }
    enum Failure { NETWORK, TIMEOUT, SECURITY, BLOCKED, OTHER }
    Phase phase = Phase.IDLE;
    Failure failure = Failure.OTHER;
    int progress;

    void start() { phase = Phase.LOADING; progress = 0; failure = Failure.OTHER; }
    void progress(int value) { if (phase == Phase.LOADING) progress = Math.max(0, Math.min(100, value)); }
    void stop() { if (phase == Phase.LOADING) phase = Phase.STOPPED; }
    void complete(boolean success) {
        if (phase == Phase.STOPPED || phase == Phase.FAILED) return;
        phase = success ? Phase.READY : Phase.FAILED;
        if (success) progress = 100;
    }
    void fail(int code, int category) {
        if (phase == Phase.STOPPED) return;
        phase = Phase.FAILED;
        failure = classify(code, category);
    }

    static Failure classify(int code, int category) {
        if (category == WebRequestError.ERROR_CATEGORY_SAFEBROWSING) return Failure.BLOCKED;
        if (category == WebRequestError.ERROR_CATEGORY_SECURITY) return Failure.SECURITY;
        if (code == WebRequestError.ERROR_NET_TIMEOUT) return Failure.TIMEOUT;
        if (category == WebRequestError.ERROR_CATEGORY_NETWORK || category == WebRequestError.ERROR_CATEGORY_PROXY
            || code == WebRequestError.ERROR_UNKNOWN_HOST) return Failure.NETWORK;
        return Failure.OTHER;
    }
}
