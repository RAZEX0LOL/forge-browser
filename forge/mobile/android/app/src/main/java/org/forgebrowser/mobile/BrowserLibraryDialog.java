/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

final class BrowserLibraryDialog extends Dialog {
    interface OpenLink { void open(String url); }
    private final BrowserLibraryStore store;
    private final OpenLink open;
    private final boolean privateMode;
    private boolean bookmarks;
    private final List<BrowserLibrary.Entry> entries = new ArrayList<>();
    private final EntryAdapter adapter = new EntryAdapter();
    private EditText search;
    private TextView title, warning;
    private Button bookmarkMode, historyMode, clearHistory;
    private AlertDialog confirmation;

    BrowserLibraryDialog(Activity activity, BrowserLibraryStore store, boolean bookmarks, boolean privateMode, OpenLink open) {
        super(activity, android.R.style.Theme_Material_NoActionBar);
        this.store = store; this.bookmarks = bookmarks; this.privateMode = privateMode; this.open = open;
    }
    private int dp(int value) { return Math.round(value * getContext().getResources().getDisplayMetrics().density); }
    private Button button(LinearLayout row, int label, String tag, View.OnClickListener action) {
        Button button = new Button(getContext()); button.setText(label); button.setTag(tag);
        button.setContentDescription(getContext().getString(label)); button.setMinHeight(dp(48)); button.setOnClickListener(action);
        row.addView(button, new LinearLayout.LayoutParams(0, -2, 1)); return button;
    }
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (privateMode) getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE | WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
        LinearLayout root = new LinearLayout(getContext()); root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(14, 20, 17)); root.setPadding(dp(12), dp(8), dp(12), dp(8));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(dp(12) + insets.getSystemWindowInsetLeft(), dp(8) + insets.getSystemWindowInsetTop(),
                dp(12) + insets.getSystemWindowInsetRight(), dp(8) + insets.getSystemWindowInsetBottom()); return insets;
        });
        title = new TextView(getContext()); title.setTextColor(Color.WHITE); title.setTextSize(22); root.addView(title);
        LinearLayout modes = new LinearLayout(getContext());
        bookmarkMode = button(modes, R.string.bookmarks, "forge-library-bookmarks", v -> changeMode(true));
        historyMode = button(modes, R.string.history, "forge-library-history", v -> changeMode(false)); root.addView(modes);
        search = new EditText(getContext()); search.setSingleLine(true); search.setTag("forge-library-search");
        search.setHint(R.string.search_library); search.setContentDescription(getContext().getString(R.string.search_library));
        search.setTextColor(Color.WHITE); search.setHintTextColor(Color.LTGRAY); search.setSaveEnabled(false);
        search.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        search.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        search.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH | android.view.inputmethod.EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
        root.addView(search, new LinearLayout.LayoutParams(-1, dp(56)));
        warning = new TextView(getContext()); warning.setTextColor(Color.rgb(255, 190, 120)); warning.setText(R.string.library_unavailable);
        warning.setTag("forge-library-warning"); root.addView(warning);
        ListView list = new ListView(getContext()); list.setTag("forge-library-list"); list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> open(entries.get(position).url));
        root.addView(list, new LinearLayout.LayoutParams(-1, 0, 1));
        TextView empty = new TextView(getContext()); empty.setText(R.string.library_empty); empty.setTextColor(Color.LTGRAY);
        empty.setTag("forge-library-empty"); root.addView(empty); list.setEmptyView(empty);
        LinearLayout actions = new LinearLayout(getContext());
        clearHistory = button(actions, R.string.clear_history, "forge-library-clear-history", v -> confirmClearHistory());
        button(actions, R.string.done, "forge-library-done", v -> dismiss()); root.addView(actions);
        search.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { refresh(); }
            @Override public void afterTextChanged(android.text.Editable s) {}
        });
        setContentView(root); root.setFocusableInTouchMode(true); root.requestFocus(); refresh();
    }
    @Override protected void onStart() { super.onStart(); getWindow().setLayout(-1, -1); refresh(); }
    @Override public void dismiss() { if (confirmation != null) confirmation.dismiss(); super.dismiss(); }
    private void changeMode(boolean value) { bookmarks = value; search.setText(""); refresh(); }
    private void open(String url) { dismiss(); open.open(url); }
    private void refresh() {
        if (search == null) return;
        title.setText(bookmarks ? R.string.bookmarks : R.string.history);
        bookmarkMode.setEnabled(!bookmarks); historyMode.setEnabled(bookmarks);
        bookmarkMode.setSelected(bookmarks); historyMode.setSelected(!bookmarks);
        BrowserLibrary snapshot = store.snapshot();
        String query = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        entries.clear();
        for (BrowserLibrary.Entry entry : bookmarks ? snapshot.bookmarks() : snapshot.history()) {
            if (query.isEmpty() || entry.title.toLowerCase(Locale.ROOT).contains(query)
                || entry.url.toLowerCase(Locale.ROOT).contains(query)) entries.add(entry);
        }
        warning.setVisibility(store.isAvailable() ? View.GONE : View.VISIBLE);
        clearHistory.setVisibility(bookmarks ? View.GONE : View.VISIBLE);
        clearHistory.setEnabled(store.isAvailable() && !snapshot.history().isEmpty()); adapter.notifyDataSetChanged();
    }
    private void confirmClearHistory() {
        confirmation = new AlertDialog.Builder(getContext()).setTitle(R.string.clear_history).setMessage(R.string.clear_history_warning)
            .setNegativeButton(android.R.string.cancel, null).setPositiveButton(R.string.clear_history, (dialog, which) -> {
                try { store.clearHistory(); } catch (java.io.IOException | org.json.JSONException error) { /* Warning remains visible. */ }
                refresh();
            }).create();
        if (privateMode) confirmation.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        confirmation.setOnShowListener(dialog -> confirmation.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
        confirmation.show();
    }
    private final class EntryAdapter extends BaseAdapter {
        @Override public int getCount() { return entries.size(); }
        @Override public BrowserLibrary.Entry getItem(int position) { return entries.get(position); }
        @Override public long getItemId(int position) { return position; }
        @Override public View getView(int position, View recycled, ViewGroup parent) {
            BrowserLibrary.Entry entry = getItem(position);
            boolean bookmark = bookmarks;
            String name = entry.title.isEmpty() ? entry.url : entry.title;
            LinearLayout row = new LinearLayout(getContext()); row.setGravity(android.view.Gravity.CENTER_VERTICAL);
            row.setTag("forge-library-entry-" + entry.id); row.setPadding(dp(8), dp(8), dp(8), dp(8));
            TextView label = new TextView(getContext()); label.setTextColor(Color.WHITE); label.setTextSize(16); label.setMaxLines(4);
            label.setText(getContext().getString(R.string.tab_overview_entry, name, entry.url));
            label.setFocusable(true); label.setOnClickListener(v -> open(entry.url));
            row.addView(label, new LinearLayout.LayoutParams(0, -2, 1));
            Button delete = new Button(getContext()); delete.setText("×"); delete.setTag("forge-library-delete-" + entry.id);
            delete.setContentDescription(getContext().getString(R.string.delete_library_entry, name)); delete.setEnabled(store.isAvailable());
            delete.setOnClickListener(v -> {
                try { store.remove(entry.id, bookmark); } catch (java.io.IOException | org.json.JSONException error) { /* Warning remains visible. */ }
                refresh();
            });
            row.addView(delete, new LinearLayout.LayoutParams(dp(52), dp(52))); return row;
        }
    }
}
