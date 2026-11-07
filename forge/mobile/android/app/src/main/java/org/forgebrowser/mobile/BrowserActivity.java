/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
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
import android.widget.ProgressBar;
import java.util.List;
import java.util.HashMap;
import java.util.Map;
import java.io.IOException;
import org.json.JSONException;
import org.mozilla.geckoview.AllowOrDeny;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoRuntime;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoSessionSettings;
import org.mozilla.geckoview.GeckoView;
import org.mozilla.geckoview.WebResponse;
import org.mozilla.geckoview.StorageController;

public final class BrowserActivity extends Activity {
    private static GeckoRuntime runtime;
    private static BrowserLibraryStore libraryStore;
    private static final Map<BrowserActivity, Boolean> activities = new java.util.WeakHashMap<>();
    private static boolean clearingSiteData;
    static final long SITE_DATA_FLAGS = StorageController.ClearFlags.COOKIES
        | StorageController.ClearFlags.ALL_CACHES | StorageController.ClearFlags.DOM_STORAGES
        | StorageController.ClearFlags.AUTH_SESSIONS;
    interface SiteDataClearer { GeckoResult<Void> clear(long flags); }
    SiteDataClearer siteDataClearer = flags -> runtime.getStorageController().clearData(flags);
    private GeckoSession session;
    private GeckoView browser;
    private EditText address;
    private TextView status;
    private Button back, forward, tabsButton, reloadButton;
    private ProgressBar pageProgress;
    private boolean canGoBack;
    private BrowserSessionStore sessionStore;
    private RetainedTabs state;
    private int statusResource = R.string.prototype;
    private android.app.Dialog tabDialog;
    private LinearLayout downloadPanel;
    private TextView downloadStatus;
    private ProgressBar downloadProgress;
    private Button startDownload, saveDownload, cancelDownload;
    private static final int SAVE_DOWNLOAD = 41;
    private BrowserPermissions permissions;
    private BrowserUploads uploads;
    private boolean foreground;
    private boolean resumed;
    private String pendingExternalLink;
    private AlertDialog externalLinkDialog;
    private long linkActionVersion;
    private LinearLayout findPanel;
    private EditText findQuery;
    private TextView findStatus;
    private GeckoSession findSession;
    private long findVersion;

    private static final class TabRuntime {
        final GeckoSession session;
        final boolean privatePage;
        TabRuntime(boolean privatePage) {
            this.privatePage = privatePage;
            session = new GeckoSession(new GeckoSessionSettings.Builder().usePrivateMode(privatePage).build());
        }
        boolean pendingLoad, canGoBack, canGoForward, userNavigationStarted;
        String secureOrigin;
        long permissionVersion;
        boolean mediaGranted;
        boolean externalResponse;
        String requestedAddress, documentAddress;
        boolean ignoringInitialBlank;
        final BrowserNavigationState navigation = new BrowserNavigationState();
    }

    private static final class RetainedTabs {
        BrowserTabs tabs = new BrowserTabs();
        BrowserTabs regularTabs = tabs;
        BrowserTabs privateTabs = new BrowserTabs();
        boolean privateBrowsing;
        final Map<String, TabRuntime> pages = new HashMap<>();
        boolean persistenceEnabled = true;
        String lastPersistedRegularSession;
        BrowserDownloads downloads;
        boolean savePickerOpen;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private Button button(LinearLayout row, int label, View.OnClickListener action) {
        Button button = new Button(this);
        button.setText(label);
        button.setContentDescription(getString(label));
        button.setOnClickListener(action);
        button.setMinWidth(0);
        button.setTextSize(12);
        button.setPadding(dp(4), 0, dp(4), 0);
        row.addView(button, new LinearLayout.LayoutParams(0, dp(52), 1));
        return button;
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
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
        address.setTag("forge-address");
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
        Button go = new Button(this);
        go.setText(R.string.go);
        go.setContentDescription(getString(R.string.go));
        go.setTag("forge-go");
        go.setOnClickListener(v -> { if (address.hasFocus()) cancelAddressEditing(); else navigate(); });
        address.setOnFocusChangeListener((view, focused) -> {
            go.setText(focused ? android.R.string.cancel : R.string.go);
            go.setContentDescription(getString(focused ? R.string.cancel_address_editing : R.string.go));
            go.setTag(focused ? "forge-address-cancel" : "forge-go");
            if (!focused && state != null) refreshControls();
        });
        toolbar.addView(go);
        root.addView(toolbar);
        findPanel = new LinearLayout(this);
        findPanel.setTag("forge-find-panel");
        findPanel.setOrientation(LinearLayout.VERTICAL);
        findPanel.setVisibility(View.GONE);
        findQuery = new EditText(this);
        findQuery.setTag("forge-find-query");
        findQuery.setHint(R.string.find_in_page);
        findQuery.setContentDescription(getString(R.string.find_in_page));
        findQuery.setTextColor(Color.WHITE);
        findQuery.setHintTextColor(Color.LTGRAY);
        findQuery.setSingleLine(true);
        findQuery.setSaveEnabled(false);
        findQuery.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        findQuery.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        findQuery.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(512)});
        findQuery.setImeOptions(EditorInfo.IME_ACTION_SEARCH | EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
        findPanel.addView(findQuery, new LinearLayout.LayoutParams(-1, dp(48)));
        findStatus = new TextView(this);
        findStatus.setTag("forge-find-status");
        findStatus.setTextColor(Color.LTGRAY);
        findStatus.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        findPanel.addView(findStatus);
        LinearLayout findActions = new LinearLayout(this);
        button(findActions, R.string.find_previous, v -> findInPage(true));
        button(findActions, R.string.find_next, v -> findInPage(false));
        Button closeFind = button(findActions, R.string.done, v -> closeFindInPage());
        closeFind.setTag("forge-find-done");
        findPanel.addView(findActions);
        root.addView(findPanel);
        findQuery.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { findInPage(false); }
            @Override public void afterTextChanged(android.text.Editable s) {}
        });
        findQuery.setOnEditorActionListener((view, action, event) -> {
            if (action != EditorInfo.IME_ACTION_SEARCH) return false;
            findInPage(false); return true;
        });
        status = new TextView(this);
        status.setTag("forge-status");
        status.setTextColor(Color.LTGRAY);
        status.setText(R.string.prototype);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        root.addView(status);
        pageProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        pageProgress.setTag("forge-page-progress");
        pageProgress.setMax(100);
        pageProgress.setVisibility(View.GONE);
        root.addView(pageProgress, new LinearLayout.LayoutParams(-1, dp(3)));
        downloadPanel = new LinearLayout(this);
        downloadPanel.setOrientation(LinearLayout.VERTICAL);
        downloadPanel.setVisibility(View.GONE);
        downloadStatus = new TextView(this);
        downloadStatus.setTextColor(Color.WHITE);
        downloadStatus.setTag("forge-download-status");
        downloadStatus.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        downloadPanel.addView(downloadStatus);
        downloadProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        downloadProgress.setMax(1000);
        downloadPanel.addView(downloadProgress);
        LinearLayout downloadActions = new LinearLayout(this);
        startDownload = button(downloadActions, R.string.download_start, v -> state.downloads.start());
        saveDownload = button(downloadActions, R.string.download_save, v -> chooseDownloadDestination());
        cancelDownload = button(downloadActions, R.string.download_cancel, v -> state.downloads.cancel());
        downloadPanel.addView(downloadActions);
        root.addView(downloadPanel);
        browser = new GeckoView(this);
        browser.setTag("forge-browser");
        root.addView(browser, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout navigation = new LinearLayout(this);
        back = button(navigation, R.string.back, v -> session.goBack()); back.setEnabled(false);
        forward = button(navigation, R.string.forward, v -> session.goForward()); forward.setEnabled(false);
        reloadButton = button(navigation, R.string.reload, v -> {
            TabRuntime page = state.pages.get(state.tabs.selectedId());
            if (page != null && page.navigation.phase == BrowserNavigationState.Phase.LOADING) stopLoadingSelected();
            else reloadSelected();
        });
        reloadButton.setTag("forge-reload");
        tabsButton = button(navigation, R.string.tabs, v -> showTabs());
        tabsButton.setTag("forge-tabs");
        Button menu = button(navigation, R.string.browser_menu, v -> showMenu());
        menu.setTag("forge-menu");
        root.addView(navigation);
        root.setFocusableInTouchMode(true);
        root.requestFocus();
        setContentView(root);
        if (runtime == null) runtime = GeckoRuntime.create(getApplicationContext());
        if (libraryStore == null) libraryStore = new BrowserLibraryStore(getNoBackupFilesDir());
        Object retained = getLastNonConfigurationInstance();
        state = retained instanceof RetainedTabs ? (RetainedTabs) retained : new RetainedTabs();
        permissions = new BrowserPermissions(this, () -> clearingSiteData || !foreground || state.savePickerOpen
            || (tabDialog != null && tabDialog.isShowing()) || state.downloads.stage == BrowserDownloads.Stage.CONFIRM);
        activities.put(this, true);
        if (state.downloads == null) state.downloads = new BrowserDownloads(getApplicationContext());
        uploads = new BrowserUploads(this, new BrowserUploads.Host() {
            @Override public boolean current(GeckoSession source, String document, long version) {
                TabRuntime page = state.pages.get(state.tabs.selectedId());
                return !clearingSiteData && !isFinishing() && page != null && session == source
                    && page.session == source && source.isOpen() && page.permissionVersion == version
                    && document.equals(page.documentAddress) && page.navigation.phase == BrowserNavigationState.Phase.READY;
            }
            @Override public void unavailable() { showStatus(R.string.upload_unavailable); }
        });
        state.downloads.listener = this::refreshDownloads;
        refreshDownloads();
        sessionStore = new BrowserSessionStore(getNoBackupFilesDir());
        if (retained == null) {
            try {
                BrowserTabs saved = sessionStore.load();
                if (saved != null) {
                    state.tabs = saved; state.regularTabs = saved;
                    state.lastPersistedRegularSession = saved.encode();
                }
            } catch (IOException | JSONException error) { state.persistenceEnabled = false; }
        }
        for (Map.Entry<String, TabRuntime> item : state.pages.entrySet()) bind(item.getKey(), item.getValue());
        if (clearingSiteData) {
            setControlsEnabled(getWindow().getDecorView(), false);
            showStatus(R.string.site_data_clearing);
        } else { activateSelected(false); }
        Intent incoming = getIntent();
        // Preserve the OS launch filter identity used by lifecycle/restoration,
        // but discard untrusted payloads and grants. Android may retain the
        // original launch URL independently; Forge does not persist a URL queue.
        Intent identity = incoming == null ? new Intent().setComponent(getComponentName()) : incoming.cloneFilter();
        identity.replaceExtras((Bundle)null);
        identity.setClipData(null);
        identity.setSelector(null);
        identity.setFlags(0);
        setIntent(identity);
        if (savedInstanceState == null) receiveExternalIntent(incoming);
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        // A warm VIEW is consumed explicitly, not installed as a future launch
        // intent or saved in the Activity state.
        receiveExternalIntent(intent);
    }

    void receiveExternalIntent(Intent intent) {
        if (intent == null || !Intent.ACTION_VIEW.equals(intent.getAction()) || clearingSiteData
            || pendingExternalLink != null || (tabDialog != null && tabDialog.isShowing())) return;
        String url = BrowserExternalLinks.fromViewIntent(intent.getAction(), intent.getDataString());
        if (url == null) { showStatus(R.string.blocked); return; }
        // Only one bounded in-memory address. Never consume extras, ClipData,
        // referrers, headers or URI grants from another application.
        permissions.cancel();
        closeFindInPage();
        pendingExternalLink = url;
        presentPendingExternalLink();
    }

    private void presentPendingExternalLink() {
        if (pendingExternalLink == null || !resumed || !hasWindowFocus() || state == null) return;
        if (clearingSiteData || isFinishing() || isDestroyed() || (tabDialog != null && tabDialog.isShowing())) {
            pendingExternalLink = null; return;
        }
        final String url = pendingExternalLink;
        pendingExternalLink = null;
        final boolean privateMode = state.privateBrowsing;
        final String selected = state.tabs.selectedId();
        final long version = linkActionVersion;
        String host = android.net.Uri.parse(url).getHost();
        AlertDialog confirmation = new AlertDialog.Builder(this).setTitle(R.string.external_link_title)
            .setMessage(getString(privateMode ? R.string.external_link_private_warning : R.string.external_link_warning, host))
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.open_link_new_tab, (dialog, which) -> {
                if (!resumed || !foreground || clearingSiteData || isFinishing() || isDestroyed()
                    || linkActionVersion != version || state.privateBrowsing != privateMode
                    || !selected.equals(state.tabs.selectedId()) || !hasBrowserFocus()) return;
                if (!addTab()) return;
                address.setText(url); navigate();
            }).create();
        if (privateMode) confirmation.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        confirmation.getWindow().getDecorView().setTag("forge-external-link-confirmation");
        confirmation.setOnShowListener(dialog -> confirmation.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
        confirmation.setOnDismissListener(dialog -> { if (externalLinkDialog == confirmation) externalLinkDialog = null; });
        externalLinkDialog = confirmation;
        tabDialog = confirmation;
        confirmation.show();
    }

    private void showStatus(int resource) {
        statusResource = resource;
        String message = state.persistenceEnabled ? getString(resource)
            : getString(R.string.status_with_storage_error, getString(resource), getString(R.string.session_unavailable));
        if (!libraryStore.isAvailable() && resource != R.string.library_unavailable)
            message = getString(R.string.status_with_storage_error, message, getString(R.string.library_unavailable));
        status.setText(message);
        status.setVisibility(state.persistenceEnabled && libraryStore.isAvailable() && (resource == R.string.prototype || resource == R.string.loading
            || resource == R.string.ready) ? View.GONE : View.VISIBLE);
    }

    private void persistSession() {
        if (!state.persistenceEnabled) return;
        try {
            String encoded = state.regularTabs.encode();
            if (encoded.equals(state.lastPersistedRegularSession)) return;
            sessionStore.save(state.regularTabs);
            state.lastPersistedRegularSession = encoded;
        }
        catch (IOException | JSONException error) {
            state.persistenceEnabled = false;
            showStatus(statusResource);
        }
    }

    private void bind(String id, TabRuntime page) {
        page.session.setPromptDelegate(new GeckoSession.PromptDelegate() {
            @Override public GeckoResult<PromptResponse> onFilePrompt(GeckoSession source, FilePrompt prompt) {
                if (!resumed || !foreground || state.savePickerOpen || (tabDialog != null && tabDialog.isShowing()))
                    return GeckoResult.fromValue(prompt.dismiss());
                return uploads.request(source, page.documentAddress, page.permissionVersion, prompt);
            }
        });
        BrowserTabs owner = page.privatePage ? state.privateTabs : state.regularTabs;
        page.session.setNavigationDelegate(new GeckoSession.NavigationDelegate() {
            @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession current, LoadRequest request) {
                // Do not replay auxiliary-window requests: LoadRequest exposes no
                // method/body, so a user-submitted POST cannot safely become GET.
                if (request.target == TARGET_WINDOW_NEW) return GeckoResult.fromValue(AllowOrDeny.DENY);
                boolean allowed = !clearingSiteData && state.pages.get(id) == page && NavigationPolicy.allows(request.uri);
                if (allowed) {
                    uploads.navigation(current);
                    if (request.hasUserGesture && "about:blank".equals(request.uri)) page.requestedAddress = request.uri;
                    page.documentAddress = null;
                    page.secureOrigin = null;
                    page.permissionVersion++;
                    if (current == session) permissions.cancel();
                }
                if (!allowed && current == session) showStatus(R.string.blocked);
                return GeckoResult.fromValue(allowed ? AllowOrDeny.ALLOW : AllowOrDeny.DENY);
            }
            @Override public void onLocationChange(GeckoSession current, String url,
                List<GeckoSession.PermissionDelegate.ContentPermission> contentPermissions, Boolean gesture) {
                if (clearingSiteData || state.pages.get(id) != page || ("about:blank".equals(url)
                    && (page.pendingLoad || awaitingRequestedPage(page)))) return;
                if (!java.util.Objects.equals(BrowserPermissions.origin(url), page.secureOrigin)) {
                    page.secureOrigin = null;
                    page.permissionVersion++;
                    if (current == session) permissions.cancel();
                }
                if (url != null && owner.update(id, url, null)) {
                    page.documentAddress = url;
                    if (!"about:blank".equals(url)) page.requestedAddress = null;
                    persistSession();
                }
                if (current == session) refreshControls();
            }
            @Override public void onCanGoBack(GeckoSession current, boolean value) {
                page.canGoBack = value;
                if (current == session) { canGoBack = value; back.setEnabled(value); }
            }
            @Override public void onCanGoForward(GeckoSession current, boolean value) {
                page.canGoForward = value;
                if (current == session) forward.setEnabled(value);
            }
            @Override public GeckoResult<String> onLoadError(GeckoSession current, String uri, org.mozilla.geckoview.WebRequestError error) {
                if (clearingSiteData || state.pages.get(id) != page) return null;
                page.secureOrigin = null;
                page.navigation.fail(error.code, error.category);
                if (current == session) { permissions.cancel(); refreshNavigation(); }
                return null; // Preserve Gecko's own error document and security interstitials.
            }
        });
        page.session.setContentDelegate(new GeckoSession.ContentDelegate() {
            @Override public void onContextMenu(GeckoSession current, int screenX, int screenY, ContextElement element) {
                if (element == null || BrowserLinkActions.shareURL(element.linkUri) == null
                    || !canOpenLinkFrom(id, page) || (tabDialog != null && tabDialog.isShowing())) return;
                final long version = page.permissionVersion;
                final long actionVersion = linkActionVersion;
                final String url = element.linkUri;
                AlertDialog menu = new AlertDialog.Builder(BrowserActivity.this)
                    .setTitle(R.string.open_link_new_tab)
                    .setMessage(url)
                    .setNegativeButton(android.R.string.cancel, null)
                    .setPositiveButton(R.string.open_link_new_tab, (dialog, which) -> {
                        if (page.permissionVersion == version && linkActionVersion == actionVersion)
                            openLinkInNewTab(url, id, page);
                    }).create();
                if (page.privatePage) menu.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
                menu.setOnShowListener(dialog -> menu.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
                tabDialog = menu;
                menu.show();
            }
            @Override public void onExternalResponse(GeckoSession current, WebResponse response) {
                page.externalResponse = true;
                if (clearingSiteData || state.pages.get(id) != page || page.privatePage || current != session || !hasWindowFocus()) {
                    if (page.privatePage && current == session) showStatus(R.string.private_download_blocked);
                    new Thread(() -> { if (response.body != null) try { response.body.close(); }
                        catch (IOException ignored) { } }, "forge-download-reject").start();
                    return;
                }
                if (!state.downloads.offer(response)) showStatus(R.string.download_rejected);
            }
            @Override public void onTitleChange(GeckoSession current, String title) {
                if (clearingSiteData || state.pages.get(id) != page || page.pendingLoad) return;
                if (owner.update(id, null, title)) persistSession();
            }
        });
        page.session.setProgressDelegate(new GeckoSession.ProgressDelegate() {
            @Override public void onSecurityChange(GeckoSession current, SecurityInformation information) {
                if (state.pages.get(id) != page) return;
                page.secureOrigin = information.isSecure && !information.isException
                    ? BrowserPermissions.origin(information.origin) : null;
                if (page.secureOrigin == null && current == session) permissions.cancel();
            }
            @Override public void onPageStart(GeckoSession current, String url) {
                if (clearingSiteData || state.pages.get(id) != page || !page.userNavigationStarted) return;
                page.ignoringInitialBlank = "about:blank".equals(url) && awaitingRequestedPage(page);
                if (page.ignoringInitialBlank) return;
                uploads.navigation(current);
                page.permissionVersion++;
                page.navigation.start();
                page.externalResponse = false;
                if (current == session) refreshNavigation();
            }
            @Override public void onProgressChange(GeckoSession current, int progress) {
                if (clearingSiteData || state.pages.get(id) != page || page.ignoringInitialBlank) return;
                page.navigation.progress(progress);
                if (current == session) refreshNavigation();
            }
            @Override public void onPageStop(GeckoSession current, boolean success) {
                if (clearingSiteData || state.pages.get(id) != page) return;
                if (page.ignoringInitialBlank) { page.ignoringInitialBlank = false; return; }
                if (!success) { page.secureOrigin = null; if (current == session) permissions.cancel(); }
                if (!page.userNavigationStarted) return;
                page.navigation.complete(success);
                if (current == session) refreshNavigation();
                BrowserTabs.Tab visited = owner.find(id);
                if (success && page.navigation.phase == BrowserNavigationState.Phase.READY && !page.externalResponse
                    && visited != null && visited.url().equals(page.documentAddress) && !page.privatePage) {
                    try { libraryStore.recordVisit(visited.url(), visited.title(), false); }
                    catch (IOException | JSONException error) { if (current == session) showStatus(R.string.library_unavailable); }
                }
            }
        });
        page.session.setPermissionDelegate(new GeckoSession.PermissionDelegate() {
            private java.util.function.BooleanSupplier valid(long version, String origin) {
                return () -> foreground && !clearingSiteData && state.pages.get(id) == page && currentTab(id)
                    && page.permissionVersion == version && origin != null && origin.equals(page.secureOrigin);
            }
            @Override public void onAndroidPermissionsRequest(GeckoSession current, String[] requested, Callback callback) {
                String origin = page.secureOrigin;
                permissions.requestSystem(origin, requested, valid(page.permissionVersion, origin),
                    allowed -> { if (allowed) callback.grant(); else callback.reject(); });
            }
            @Override public GeckoResult<Integer> onContentPermissionRequest(GeckoSession current, ContentPermission permission) {
                if (current == session) showStatus(R.string.permission_unsupported);
                return GeckoResult.fromValue(ContentPermission.VALUE_DENY);
            }
            @Override public void onMediaPermissionRequest(GeckoSession current, String uri, MediaSource[] video,
                MediaSource[] audio, MediaCallback callback) {
                String origin = BrowserPermissions.origin(uri);
                if (origin == null || !origin.equals(page.secureOrigin)) { callback.reject(); return; }
                MediaSource camera = source(video, MediaSource.SOURCE_CAMERA, MediaSource.TYPE_VIDEO);
                MediaSource microphone = source(audio, MediaSource.SOURCE_MICROPHONE, MediaSource.TYPE_AUDIO);
                if ((video != null && (video.length == 0 || camera == null))
                    || (audio != null && (audio.length == 0 || microphone == null))) { callback.reject(); return; }
                permissions.requestMedia(origin, camera != null, microphone != null, valid(page.permissionVersion, origin), allowed -> {
                    if (allowed) { page.mediaGranted = true; callback.grant(camera, microphone); }
                    else callback.reject();
                });
            }
        });
    }

    private boolean currentTab(String id) { return session != null && id.equals(state.tabs.selectedId()); }

    private static boolean awaitingRequestedPage(TabRuntime page) {
        return page.requestedAddress != null && !page.requestedAddress.equals("about:blank");
    }

    private static GeckoSession.PermissionDelegate.MediaSource source(GeckoSession.PermissionDelegate.MediaSource[] sources, int source, int type) {
        if (sources == null) return null;
        for (GeckoSession.PermissionDelegate.MediaSource value : sources)
            if (value != null && value.id != null && value.source == source && value.type == type) return value;
        return null;
    }

    private void stopMediaSessions(String keepID) {
        for (String id : new java.util.ArrayList<>(state.pages.keySet())) {
            TabRuntime page = state.pages.get(id);
            if ((!page.mediaGranted && !uploads.hasAccess(page.session)) || id.equals(keepID)) continue;
            if (browser.getSession() == page.session) { browser.releaseSession(); session = null; }
            page.session.setPermissionDelegate(null);
            page.session.setNavigationDelegate(null);
            page.session.setProgressDelegate(null);
            page.session.setContentDelegate(null);
            page.session.close();
            uploads.engineClosed(page.session);
            state.pages.remove(id);
        }
    }

    private void refreshControls() {
        BrowserTabs.Tab tab = state.tabs.selected();
        if (!address.hasFocus()) address.setText(tab.url().equals("about:blank") ? "" : tab.url());
        TabRuntime page = state.pages.get(tab.id);
        canGoBack = page != null && page.canGoBack;
        back.setEnabled(canGoBack);
        forward.setEnabled(page != null && page.canGoForward);
        String label = getString(R.string.tab_count, state.tabs.all().size());
        if (state.privateBrowsing) label = getString(R.string.private_browsing) + " · " + label;
        tabsButton.setText(label);
        tabsButton.setContentDescription(label);
        refreshNavigation();
    }

    private void refreshNavigation() {
        if (clearingSiteData || state == null) return;
        TabRuntime page = state.pages.get(state.tabs.selectedId());
        BrowserNavigationState navigation = page == null ? null : page.navigation;
        boolean loading = navigation != null && navigation.phase == BrowserNavigationState.Phase.LOADING;
        reloadButton.setText(loading ? R.string.stop_button : R.string.reload);
        reloadButton.setContentDescription(getString(loading ? R.string.stop_loading : R.string.reload));
        reloadButton.setTag(loading ? "forge-stop" : "forge-reload");
        pageProgress.setVisibility(loading ? View.VISIBLE : View.GONE);
        pageProgress.setProgress(navigation == null ? 0 : navigation.progress);
        if (navigation == null || navigation.phase == BrowserNavigationState.Phase.IDLE) return;
        switch (navigation.phase) {
            case LOADING: showStatus(R.string.loading); break;
            case READY: showStatus(R.string.ready); break;
            case STOPPED: showStatus(R.string.loading_stopped); break;
            case FAILED:
                switch (navigation.failure) {
                    case SECURITY: showStatus(R.string.connection_secure_failed); break;
                    case TIMEOUT: showStatus(R.string.connection_timed_out); break;
                    case NETWORK: showStatus(R.string.connection_failed); break;
                    case BLOCKED: showStatus(R.string.site_blocked); break;
                    default: showStatus(R.string.load_failed);
                }
                break;
            default: break;
        }
    }

    void cancelAddressEditing() {
        if (state == null) return;
        address.clearFocus();
        address.setText(state.tabs.selected().url().equals("about:blank") ? "" : state.tabs.selected().url());
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(address.getWindowToken(), 0);
    }

    void stopLoadingSelected() {
        if (clearingSiteData) return;
        TabRuntime page = state.pages.get(state.tabs.selectedId());
        if (page == null) return;
        permissions.cancel();
        page.navigation.stop();
        page.session.stop();
        refreshNavigation();
    }

    private void activateSelected(boolean loadSavedPage) {
        if (clearingSiteData) return;
        closeFindInPage();
        uploads.cancel();
        permissions.cancel();
        stopMediaSessions(state.tabs.selectedId());
        if (state.privateBrowsing) getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        else getWindow().clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        address.clearFocus();
        BrowserTabs.Tab tab = state.tabs.selected();
        TabRuntime page = state.pages.get(tab.id);
        if (page == null) {
            page = new TabRuntime(state.privateBrowsing);
            page.pendingLoad = !tab.url().equals("about:blank");
            state.pages.put(tab.id, page);
            bind(tab.id, page);
            page.session.open(runtime);
        }
        if (browser.getSession() != null) browser.releaseSession();
        if (session != null && session.isOpen()) session.setActive(false);
        session = page.session;
        browser.setSession(session);
        session.setActive(true);
        refreshControls();
        showStatus(page.pendingLoad ? R.string.session_restored : R.string.prototype);
        if (page.pendingLoad && loadSavedPage) reloadSelected();
    }

    private void reloadSelected() {
        if (clearingSiteData) return;
        if (state.tabs.selected().url().equals("about:blank")) return;
        if (uploads.hasAccess(session)) {
            stopMediaSessions(null);
            activateSelected(false);
        }
        TabRuntime page = state.pages.get(state.tabs.selectedId());
        page.userNavigationStarted = true;
        page.requestedAddress = state.tabs.selected().url();
        page.documentAddress = null;
        page.ignoringInitialBlank = false;
        page.navigation.start();
        refreshNavigation();
        if (page.pendingLoad) {
            page.pendingLoad = false;
            session.loadUri(state.tabs.selected().url());
        } else { session.reload(); }
    }

    boolean addTab() {
        if (clearingSiteData) return false;
        if (state.tabs.add() == null) { showStatus(R.string.tab_limit); return false; }
        persistSession();
        activateSelected(false);
        return true;
    }

    private boolean canOpenLinkFrom(String id, TabRuntime page) {
        return !clearingSiteData && foreground && hasBrowserFocus() && !isFinishing() && !isDestroyed()
            && state.pages.get(id) == page && currentTab(id) && session == page.session
            && page.privatePage == state.privateBrowsing && !page.pendingLoad
            && BrowserLinkActions.shareURL(state.tabs.selected().url()) != null;
    }

    private boolean hasBrowserFocus() {
        return hasWindowFocus() || (tabDialog != null && tabDialog.isShowing()
            && tabDialog.getWindow().getDecorView().hasWindowFocus());
    }

    private boolean openLinkInNewTab(String url, String id, TabRuntime page) {
        // An explicit link address becomes a fresh native session, without opener,
        // referrer, form data or content-supplied request headers.
        if (!canOpenLinkFrom(id, page) || BrowserLinkActions.shareURL(url) == null) return false;
        if (!addTab()) return false;
        address.setText(url);
        navigate();
        return true;
    }

    void selectTab(String id) {
        if (clearingSiteData) return;
        if (!state.tabs.select(id)) return;
        persistSession();
        activateSelected(true);
    }

    void closeTab(String id) {
        closeTab(id, true);
    }

    private void closeTab(String id, boolean loadSavedPage) {
        if (clearingSiteData) return;
        permissions.cancel();
        if (state.tabs.find(id) == null) return;
        boolean selected = id.equals(state.tabs.selectedId());
        state.tabs.close(id);
        TabRuntime removed = state.pages.remove(id);
        if (removed != null) {
            if (browser.getSession() == removed.session) { browser.releaseSession(); session = null; }
            removed.session.setNavigationDelegate(null);
            removed.session.setPermissionDelegate(null);
            removed.session.setProgressDelegate(null);
            removed.session.setContentDelegate(null);
            removed.session.close();
            uploads.engineClosed(removed.session);
        }
        persistSession();
        if (selected) activateSelected(loadSavedPage); else refreshControls();
    }

    BrowserTabs tabsSnapshot() throws JSONException { return BrowserTabs.decode(state.tabs.encode()); }

    boolean isPrivateBrowsing() { return state.privateBrowsing; }

    void setPrivateBrowsing(boolean enabled) {
        if (clearingSiteData) return;
        if (enabled == state.privateBrowsing) return;
        if (session != null) session.stop();
        state.privateBrowsing = enabled;
        state.tabs = enabled ? state.privateTabs : state.regularTabs;
        activateSelected(false);
    }

    void closePrivateTabs() {
        if (clearingSiteData) return;
        if (state.privateBrowsing) setPrivateBrowsing(false);
        for (BrowserTabs.Tab tab : state.privateTabs.all()) {
            TabRuntime page = state.pages.remove(tab.id);
            if (page == null) continue;
            page.session.setNavigationDelegate(null);
            page.session.setProgressDelegate(null);
            page.session.setContentDelegate(null);
            page.session.close();
            uploads.engineClosed(page.session);
        }
        state.privateTabs = new BrowserTabs();
    }

    boolean isClearingSiteData() { return clearingSiteData; }

    private static boolean exportingFile() {
        for (BrowserActivity activity : new java.util.ArrayList<>(activities.keySet()))
            if (activity.state.savePickerOpen || activity.state.downloads.stage == BrowserDownloads.Stage.SAVING) return true;
        return false;
    }

    AlertDialog requestClearSiteData() {
        if (clearingSiteData) return null;
        if (exportingFile()) { showStatus(R.string.site_data_export_busy); return null; }
        if (tabDialog != null) tabDialog.dismiss();
        AlertDialog confirmation = new AlertDialog.Builder(this)
            .setTitle(R.string.site_data_clear).setMessage(R.string.site_data_warning)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.site_data_clear, (dialog, which) -> clearSiteDataConfirmed(null)).create();
        tabDialog = confirmation;
        confirmation.setOnShowListener(dialog -> confirmation.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
        confirmation.show();
        return confirmation;
    }

    void clearSiteDataConfirmed(java.util.function.Consumer<Boolean> completion) {
        if (clearingSiteData) { if (completion != null) completion.accept(false); return; }
        if (exportingFile()) {
            showStatus(R.string.site_data_export_busy);
            if (completion != null) completion.accept(false);
            return;
        }
        clearingSiteData = true;
        for (BrowserActivity activity : new java.util.ArrayList<>(activities.keySet())) activity.prepareForSiteDataClearing();
        try {
            siteDataClearer.clear(SITE_DATA_FLAGS).withHandler(new android.os.Handler(android.os.Looper.getMainLooper()))
                .accept(value -> finishSiteDataClearing(true, completion), error -> finishSiteDataClearing(false, completion));
        } catch (RuntimeException error) { finishSiteDataClearing(false, completion); }
    }

    private static void finishSiteDataClearing(boolean success, java.util.function.Consumer<Boolean> completion) {
        clearingSiteData = false;
        for (BrowserActivity activity : new java.util.ArrayList<>(activities.keySet())) {
            setControlsEnabled(activity.getWindow().getDecorView(), true);
            activity.activateSelected(false);
            activity.showStatus(success ? R.string.site_data_cleared : R.string.site_data_failed);
        }
        if (completion != null) completion.accept(success);
    }

    private void prepareForSiteDataClearing() {
        uploads.cancel();
        permissions.cancel();
        closeFindInPage();
        address.clearFocus();
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(address.getWindowToken(), 0);
        state.downloads.cancel();
        if (tabDialog != null) tabDialog.dismiss();
        if (browser.getSession() != null) browser.releaseSession();
        session = null;
        for (TabRuntime page : state.pages.values()) {
            page.session.setPermissionDelegate(null);
            page.session.setNavigationDelegate(null);
            page.session.setProgressDelegate(null);
            page.session.setContentDelegate(null);
            if (page.session.isOpen()) { page.session.stop(); page.session.close(); }
            uploads.engineClosed(page.session);
        }
        state.pages.clear();
        state.privateTabs = new BrowserTabs();
        state.privateBrowsing = false;
        state.tabs = state.regularTabs;
        canGoBack = false;
        address.setText("");
        setControlsEnabled(getWindow().getDecorView(), false);
        showStatus(R.string.site_data_clearing);
    }

    private static void setControlsEnabled(View view, boolean enabled) {
        if (view instanceof Button || view instanceof EditText) view.setEnabled(enabled);
        if (view instanceof android.view.ViewGroup) {
            android.view.ViewGroup group = (android.view.ViewGroup)view;
            for (int index = 0; index < group.getChildCount(); index++) setControlsEnabled(group.getChildAt(index), enabled);
        }
    }

    private void refreshDownloads() {
        BrowserDownloads download = state.downloads;
        downloadPanel.setVisibility(download.stage == BrowserDownloads.Stage.EMPTY ? View.GONE : View.VISIBLE);
        int label;
        switch (download.stage) {
            case CONFIRM: label = R.string.download_confirm; break;
            case RECEIVING: label = R.string.download_receiving; break;
            case READY: label = R.string.download_ready; break;
            case SAVE_FAILED: label = R.string.download_save_failed; break;
            case SAVING: label = R.string.download_saving; break;
            case SAVED: label = R.string.download_saved; break;
            case CANCELLED: label = R.string.download_cancelled; break;
            default: label = R.string.download_failed;
        }
        downloadStatus.setText(getString(R.string.download_details, download.name, getString(label),
            android.text.format.Formatter.formatShortFileSize(this, download.received)));
        boolean receiving = download.stage == BrowserDownloads.Stage.RECEIVING;
        boolean saving = download.stage == BrowserDownloads.Stage.SAVING;
        downloadProgress.setVisibility(receiving || saving ? View.VISIBLE : View.GONE);
        downloadProgress.setIndeterminate(saving || download.expected <= 0);
        downloadProgress.setProgress(download.expected > 0 ? (int)Math.min(1000, download.received * 1000 / download.expected) : 0);
        startDownload.setVisibility(download.stage == BrowserDownloads.Stage.CONFIRM ? View.VISIBLE : View.GONE);
        saveDownload.setVisibility(download.stage == BrowserDownloads.Stage.READY
            || download.stage == BrowserDownloads.Stage.SAVE_FAILED ? View.VISIBLE : View.GONE);
        saveDownload.setEnabled(!state.savePickerOpen);
        cancelDownload.setText(receiving || saving || download.stage == BrowserDownloads.Stage.CONFIRM
            ? R.string.download_cancel : R.string.download_clear);
        cancelDownload.setContentDescription(cancelDownload.getText());
        if (clearingSiteData) setControlsEnabled(getWindow().getDecorView(), false);
    }

    private void chooseDownloadDestination() {
        if (clearingSiteData) return;
        if (state.savePickerOpen) return;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream")
            .addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE, state.downloads.name);
        try {
            state.savePickerOpen = true;
            startActivityForResult(intent, SAVE_DOWNLOAD);
            refreshDownloads();
        } catch (android.content.ActivityNotFoundException error) {
            state.savePickerOpen = false;
            showStatus(R.string.download_save_failed);
            refreshDownloads();
        }
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (uploads != null && uploads.result(request, result, data)) return;
        if (request != SAVE_DOWNLOAD) return;
        state.savePickerOpen = false;
        if (result == RESULT_OK && data != null && data.getData() != null) state.downloads.save(data.getData());
        refreshDownloads();
    }

    private void showTabs() {
        if (clearingSiteData) return;
        closeFindInPage();
        permissions.cancel();
        stopMediaSessions(null);
        address.clearFocus();
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(address.getWindowToken(), 0);
        if (tabDialog != null) tabDialog.dismiss();
        tabDialog = new BrowserTabsDialog(this, new BrowserTabsDialog.Host() {
            @Override public BrowserTabs tabs() { return state.tabs; }
            @Override public boolean isPrivate() { return state.privateBrowsing; }
            @Override public void select(String id) { selectTab(id); }
            @Override public void close(String id) { closeTab(id, false); }
            @Override public void add() { addTab(); }
            @Override public void changeMode(boolean privateMode) { setPrivateBrowsing(privateMode); }
            @Override public void closePrivate() { closePrivateTabs(); }
        });
        tabDialog.setOnDismissListener(dialog -> {
            if (session == null && !clearingSiteData && !isFinishing()) activateSelected(false);
        });
        tabDialog.show();
    }

    private void showMenu() {
        if (clearingSiteData) return;
        permissions.cancel();
        if (tabDialog != null) tabDialog.dismiss();
        java.util.ArrayList<String> labels = new java.util.ArrayList<>();
        java.util.ArrayList<Runnable> actions = new java.util.ArrayList<>();
        labels.add(getString(R.string.tabs)); actions.add(this::showTabs);
        labels.add(getString(R.string.new_tab)); actions.add(() -> addTab());
        labels.add(getString(R.string.close_tab)); actions.add(() -> closeTab(state.tabs.selectedId()));
        labels.add(getString(R.string.bookmarks)); actions.add(() -> showLibrary(true));
        labels.add(getString(R.string.history)); actions.add(() -> showLibrary(false));
        if (!state.privateBrowsing && libraryStore.isAvailable() && BrowserLinkActions.shareURL(state.tabs.selected().url()) != null) {
            labels.add(getString(R.string.add_bookmark)); actions.add(this::bookmarkSelected);
        }
        if (BrowserLinkActions.shareURL(state.tabs.selected().url()) != null) {
            labels.add(getString(R.string.share_link)); actions.add(this::requestShareSelected);
        }
        TabRuntime page = state.pages.get(state.tabs.selectedId());
        if (page != null && !page.pendingLoad && page.navigation.phase == BrowserNavigationState.Phase.READY) {
            labels.add(getString(R.string.find_in_page)); actions.add(this::showFindInPage);
        }
        labels.add(getString(R.string.site_data_clear)); actions.add(this::requestClearSiteData);
        tabDialog = new AlertDialog.Builder(this).setTitle(R.string.browser_menu)
            .setItems(labels.toArray(new String[0]), (dialog, index) -> actions.get(index).run())
            .setNegativeButton(android.R.string.cancel, null).create();
        if (state.privateBrowsing) tabDialog.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        tabDialog.show();
    }

    private void showLibrary(boolean bookmarks) {
        if (clearingSiteData) return;
        permissions.cancel(); closeFindInPage(); stopMediaSessions(null); address.clearFocus();
        if (tabDialog != null) tabDialog.dismiss();
        tabDialog = new BrowserLibraryDialog(this, libraryStore, bookmarks, state.privateBrowsing, url -> {
            if (clearingSiteData || BrowserLinkActions.shareURL(url) == null) return;
            if (session == null) activateSelected(false);
            address.setText(url); navigate();
        });
        tabDialog.setOnDismissListener(dialog -> {
            if (session == null && !clearingSiteData && !isFinishing()) activateSelected(false);
        });
        tabDialog.show();
    }

    boolean bookmarkSelected() {
        if (clearingSiteData) return false;
        BrowserTabs.Tab tab = state.tabs.selected();
        try {
            boolean added = libraryStore.addBookmark(tab.url(), tab.title(), state.privateBrowsing);
            showStatus(added ? R.string.bookmark_saved : R.string.bookmark_rejected); return added;
        } catch (IOException | JSONException error) { showStatus(R.string.library_unavailable); return false; }
    }

    Intent makeShareIntent() {
        String url = BrowserLinkActions.shareURL(state.tabs.selected().url());
        return url == null ? null : new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, url);
    }

    private void requestShareSelected() {
        if (clearingSiteData || !foreground || makeShareIntent() == null) return;
        if (!state.privateBrowsing) { showShareChooser(); return; }
        String id = state.tabs.selectedId(), url = state.tabs.selected().url();
        AlertDialog confirmation = new AlertDialog.Builder(this).setTitle(R.string.share_private_link)
            .setMessage(R.string.private_share_warning).setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.share_continue, (dialog, which) -> {
                if (state.privateBrowsing && id.equals(state.tabs.selectedId()) && url.equals(state.tabs.selected().url())) showShareChooser();
            }).create();
        confirmation.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        confirmation.setOnShowListener(dialog -> confirmation.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
        tabDialog = confirmation;
        confirmation.show();
    }

    private void showShareChooser() {
        if (clearingSiteData || !foreground) return;
        Intent share = makeShareIntent();
        if (share == null) return;
        try { startActivity(Intent.createChooser(share, getString(R.string.share_link))); }
        catch (android.content.ActivityNotFoundException error) { showStatus(R.string.share_unavailable); }
    }

    void showFindInPage() {
        if (clearingSiteData || session == null || !session.isOpen()) return;
        closeFindInPage();
        address.clearFocus();
        findSession = session;
        findSession.getFinder().setDisplayFlags(GeckoSession.FINDER_DISPLAY_HIGHLIGHT_ALL);
        findPanel.setVisibility(View.VISIBLE);
        findQuery.requestFocus();
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(findQuery, InputMethodManager.SHOW_IMPLICIT);
    }

    private void findInPage(boolean backwards) {
        if (clearingSiteData || findPanel.getVisibility() != View.VISIBLE || findSession == null || findSession != session) return;
        final long version = ++findVersion;
        final GeckoSession page = findSession;
        String query = findQuery.getText().toString();
        if (query.isEmpty()) { page.getFinder().clear(); findStatus.setText(""); return; }
        page.getFinder().find(query, backwards ? GeckoSession.FINDER_FIND_BACKWARDS : GeckoSession.FINDER_FIND_FORWARD).accept(result -> runOnUiThread(() -> {
            if (version != findVersion || page != session || findPanel.getVisibility() != View.VISIBLE || !foreground) return;
            findStatus.setText(getString(R.string.find_matches, result.current, result.total));
        }), error -> runOnUiThread(() -> {
            if (version == findVersion && page == session && findPanel.getVisibility() == View.VISIBLE && foreground)
                findStatus.setText(R.string.find_unavailable);
        }));
    }

    void closeFindInPage() {
        findVersion++;
        if (findPanel == null) return;
        findPanel.setVisibility(View.GONE);
        if (findSession != null && findSession.isOpen()) {
            findSession.getFinder().clear();
            findSession.getFinder().setDisplayFlags(0);
        }
        findSession = null;
        boolean focused = findQuery.hasFocus();
        findQuery.setText(""); findQuery.clearFocus(); findStatus.setText("");
        if (focused) ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(findQuery.getWindowToken(), 0);
    }

    private void navigate() {
        if (clearingSiteData) return;
        closeFindInPage();
        try {
            String url = NavigationPolicy.fromInput(address.getText().toString());
            if (uploads.hasAccess(session)) {
                stopMediaSessions(null);
                activateSelected(false);
            }
            if (!state.tabs.update(state.tabs.selectedId(), url, "")) throw new IllegalArgumentException();
            persistSession();
            TabRuntime page = state.pages.get(state.tabs.selectedId());
            page.pendingLoad = false;
            page.userNavigationStarted = true;
            page.requestedAddress = url;
            page.documentAddress = null;
            page.ignoringInitialBlank = false;
            page.navigation.start();
            refreshNavigation();
            address.clearFocus();
            ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(address.getWindowToken(), 0);
            session.loadUri(url);
        } catch (IllegalArgumentException error) { showStatus(R.string.blocked); }
    }

    @Override public Object onRetainNonConfigurationInstance() { return state; }
    @Override public void onBackPressed() {
        if (clearingSiteData) return;
        if (findPanel.getVisibility() == View.VISIBLE) closeFindInPage();
        else if (address.hasFocus()) cancelAddressEditing();
        else if (canGoBack && session != null) session.goBack();
        else super.onBackPressed();
    }
    @Override public void onStart() {
        super.onStart();
        foreground = true;
        if (state != null && session == null && !clearingSiteData) activateSelected(false);
        if (session != null && session.isOpen()) session.setActive(true);
    }
    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        presentPendingExternalLink();
    }
    @Override protected void onPause() {
        if (uploads != null) uploads.pause();
        resumed = false;
        pendingExternalLink = null;
        linkActionVersion++;
        if (externalLinkDialog != null) externalLinkDialog.dismiss();
        super.onPause();
    }
    @Override public void onStop() {
        foreground = false;
        linkActionVersion++;
        closeFindInPage();
        if (permissions != null) permissions.cancel();
        if (state != null) stopMediaSessions(null);
        if (state != null) persistSession();
        if (state != null && !isChangingConfigurations()
            && (state.downloads.stage == BrowserDownloads.Stage.RECEIVING
                || state.downloads.stage == BrowserDownloads.Stage.CONFIRM)) state.downloads.cancel();
        if (session != null && session.isOpen()) session.setActive(false);
        super.onStop();
    }
    @Override public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        if (state == null || level < TRIM_MEMORY_RUNNING_LOW) return;
        for (String id : new java.util.ArrayList<>(state.pages.keySet())) {
            if (id.equals(state.tabs.selectedId())) continue;
            TabRuntime page = state.pages.remove(id);
            page.session.setNavigationDelegate(null);
            page.session.setPermissionDelegate(null);
            page.session.setProgressDelegate(null);
            page.session.setContentDelegate(null);
            page.session.close();
            uploads.engineClosed(page.session);
        }
    }
    @Override public void onDestroy() {
        if (uploads != null) {
            uploads.cancel();
            // Upload-bearing engines are never retained across configuration
            // changes: close access before their Activity-owned leases disappear.
            stopMediaSessions(null);
            uploads.destroy();
        }
        if (permissions != null) permissions.cancel();
        activities.remove(this);
        if (tabDialog != null) tabDialog.dismiss();
        if (browser != null) browser.releaseSession();
        if (state != null) for (TabRuntime page : state.pages.values()) {
            page.session.setPermissionDelegate(null);
            page.session.setNavigationDelegate(null);
            page.session.setProgressDelegate(null);
            page.session.setContentDelegate(null);
            page.session.setActive(false);
            if (!isChangingConfigurations()) page.session.close();
        }
        if (state != null) {
            state.downloads.listener = null;
            if (!isChangingConfigurations()) state.downloads.dispose();
        }
        super.onDestroy();
    }

    @Override public void onRequestPermissionsResult(int code, String[] requested, int[] results) {
        super.onRequestPermissionsResult(code, requested, results);
        if (permissions != null) permissions.onSystemResult(code);
    }

    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused && permissions != null) permissions.onWindowFocus();
        if (focused) presentPendingExternalLink();
    }
}
