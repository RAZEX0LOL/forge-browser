package org.forgebrowser.mobile;

import org.junit.Test;
import org.mozilla.geckoview.WebRequestError;
import static org.junit.Assert.*;

public final class BrowserNavigationStateTest {
    @Test public void newNavigationResetsOldFailureAndProgress() {
        BrowserNavigationState state = new BrowserNavigationState();
        state.fail(WebRequestError.ERROR_SECURITY_BAD_CERT, WebRequestError.ERROR_CATEGORY_SECURITY);
        state.start();
        assertEquals(BrowserNavigationState.Phase.LOADING, state.phase);
        assertEquals(BrowserNavigationState.Failure.OTHER, state.failure);
        assertEquals(0, state.progress);
    }

    @Test public void progressIsBoundedAndOnlyChangesWhileLoading() {
        BrowserNavigationState state = new BrowserNavigationState();
        state.progress(40); assertEquals(0, state.progress);
        state.start(); state.progress(-1); assertEquals(0, state.progress);
        state.progress(140); assertEquals(100, state.progress);
        state.progress(42); assertEquals(42, state.progress);
        state.complete(true); state.progress(0); assertEquals(100, state.progress);
    }

    @Test public void stopIsNotReplacedByCancelledCompletionOrLateError() {
        BrowserNavigationState state = new BrowserNavigationState();
        state.start(); state.stop(); state.complete(false);
        state.fail(WebRequestError.ERROR_NET_INTERRUPT, WebRequestError.ERROR_CATEGORY_NETWORK);
        assertEquals(BrowserNavigationState.Phase.STOPPED, state.phase);
        state.start(); state.complete(true);
        assertEquals(BrowserNavigationState.Phase.READY, state.phase);
    }

    @Test public void typedErrorSurvivesGenericFailureCompletion() {
        BrowserNavigationState state = new BrowserNavigationState();
        state.start(); state.fail(WebRequestError.ERROR_NET_TIMEOUT, WebRequestError.ERROR_CATEGORY_NETWORK);
        state.complete(false);
        assertEquals(BrowserNavigationState.Phase.FAILED, state.phase);
        assertEquals(BrowserNavigationState.Failure.TIMEOUT, state.failure);
    }

    @Test public void securityAndSafeBrowsingAreNotPresentedAsOrdinaryNetworkFailures() {
        assertEquals(BrowserNavigationState.Failure.SECURITY,
            BrowserNavigationState.classify(WebRequestError.ERROR_SECURITY_SSL, WebRequestError.ERROR_CATEGORY_SECURITY));
        assertEquals(BrowserNavigationState.Failure.BLOCKED,
            BrowserNavigationState.classify(WebRequestError.ERROR_SAFEBROWSING_PHISHING_URI, WebRequestError.ERROR_CATEGORY_SAFEBROWSING));
    }

    @Test public void networkAndUnknownErrorsHaveBoundedCategories() {
        assertEquals(BrowserNavigationState.Failure.NETWORK,
            BrowserNavigationState.classify(WebRequestError.ERROR_UNKNOWN_HOST, WebRequestError.ERROR_CATEGORY_URI));
        assertEquals(BrowserNavigationState.Failure.OTHER,
            BrowserNavigationState.classify(WebRequestError.ERROR_UNKNOWN, WebRequestError.ERROR_CATEGORY_UNKNOWN));
    }
}
