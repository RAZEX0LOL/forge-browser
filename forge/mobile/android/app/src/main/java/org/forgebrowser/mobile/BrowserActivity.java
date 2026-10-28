/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.text.InputType;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.List;
import org.mozilla.geckoview.AllowOrDeny;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoRuntime;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;

public final class BrowserActivity extends Activity {
    private static GeckoRuntime runtime;
    private GeckoSession session;
    private GeckoView browser;
    private EditText address;
    private TextView status;
    private Button back, forward;
    private boolean canGoBack;

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private Button button(LinearLayout row, int label, View.OnClickListener action) {
        Button button = new Button(this);
        button.setText(label);
        button.setContentDescription(getString(label));
        button.setOnClickListener(action);
        row.addView(button, new LinearLayout.LayoutParams(0, dp(52), 1));
        return button;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        LinearLayout toolbar = new LinearLayout(this);
        address = new EditText(this);
        address.setSingleLine(true);
        address.setTextColor(Color.WHITE);
        address.setHintTextColor(Color.LTGRAY);
        address.setHint(R.string.address);
        address.setContentDescription(getString(R.string.address));
        address.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        address.setImeOptions(EditorInfo.IME_ACTION_GO);
        address.setOnEditorActionListener((view, action, event) -> {
            if (action == EditorInfo.IME_ACTION_GO) { navigate(); return true; }
            return false;
        });
        toolbar.addView(address, new LinearLayout.LayoutParams(0, dp(56), 1));
        Button go = new Button(this); go.setText(R.string.go); go.setOnClickListener(v -> navigate());
        toolbar.addView(go);
        root.addView(toolbar);
        status = new TextView(this);
        status.setTextColor(Color.LTGRAY);
        status.setText(R.string.prototype);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        root.addView(status);
        browser = new GeckoView(this);
        root.addView(browser, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout navigation = new LinearLayout(this);
        back = button(navigation, R.string.back, v -> session.goBack()); back.setEnabled(false);
        forward = button(navigation, R.string.forward, v -> session.goForward()); forward.setEnabled(false);
        button(navigation, R.string.reload, v -> session.reload());
        root.addView(navigation);
        setContentView(root);
        if (runtime == null) runtime = GeckoRuntime.create(getApplicationContext());
        Object retained = getLastNonConfigurationInstance();
        session = retained instanceof GeckoSession ? (GeckoSession) retained : new GeckoSession();
        session.setNavigationDelegate(new GeckoSession.NavigationDelegate() {
            @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession current, LoadRequest request) {
                boolean allowed = NavigationPolicy.allows(request.uri);
                if (!allowed) status.setText(R.string.blocked);
                return GeckoResult.fromValue(allowed ? AllowOrDeny.ALLOW : AllowOrDeny.DENY);
            }
            @Override public void onLocationChange(GeckoSession current, String url,
                List<GeckoSession.PermissionDelegate.ContentPermission> permissions, Boolean gesture) {
                if (url != null) address.setText(url);
            }
            @Override public void onCanGoBack(GeckoSession current, boolean value) {
                canGoBack = value; back.setEnabled(value);
            }
            @Override public void onCanGoForward(GeckoSession current, boolean value) { forward.setEnabled(value); }
        });
        session.setProgressDelegate(new GeckoSession.ProgressDelegate() {
            @Override public void onPageStart(GeckoSession current, String url) { status.setText(R.string.loading); }
            @Override public void onPageStop(GeckoSession current, boolean success) {
                status.setText(success ? R.string.ready : R.string.load_failed);
            }
        });
        if (!session.isOpen()) session.open(runtime);
        browser.setSession(session);
        if (retained == null) session.loadUri("about:blank");
    }

    private void navigate() {
        try {
            String url = NavigationPolicy.fromInput(address.getText().toString());
            address.clearFocus();
            ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(address.getWindowToken(), 0);
            session.loadUri(url);
        } catch (IllegalArgumentException error) { status.setText(R.string.blocked); }
    }

    @Override public Object onRetainNonConfigurationInstance() { return session; }
    @Override public void onBackPressed() { if (canGoBack) session.goBack(); else super.onBackPressed(); }
    @Override public void onDestroy() {
        if (browser != null) browser.releaseSession();
        if (session != null && !isChangingConfigurations()) session.close();
        super.onDestroy();
    }
}
