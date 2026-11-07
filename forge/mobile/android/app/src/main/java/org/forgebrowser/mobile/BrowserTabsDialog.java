/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.graphics.Color;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
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

// A text-only overview; never loads favicons, websites or tab screenshots.
final class BrowserTabsDialog extends Dialog {
    interface Host {
        BrowserTabs tabs();
        boolean isPrivate();
        void select(String id);
        void close(String id);
        void add();
        void changeMode(boolean privateMode);
        void closePrivate();
    }

    private final Host host;
    private final List<BrowserTabs.Tab> visible = new ArrayList<>();
    private final TabAdapter adapter = new TabAdapter();
    private EditText search;
    private TextView heading;
    private Button regular, privateTabs, add, closePrivate;
    private AlertDialog closeConfirmation;

    BrowserTabsDialog(Activity activity, Host host) {
        super(activity, android.R.style.Theme_Material_NoActionBar);
        this.host = host;
    }

    private int dp(int value) { return Math.round(value * getContext().getResources().getDisplayMetrics().density); }

    private Button button(LinearLayout row, int label, String tag, View.OnClickListener action) {
        Button button = new Button(getContext());
        button.setText(label);
        button.setContentDescription(getContext().getString(label));
        button.setTag(tag);
        button.setMinHeight(dp(48));
        button.setOnClickListener(action);
        row.addView(button, new LinearLayout.LayoutParams(0, -2, 1));
        return button;
    }

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
            | WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_HIDDEN);
        LinearLayout root = new LinearLayout(getContext());
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(14, 20, 17));
        root.setPadding(dp(12), dp(8), dp(12), dp(8));
        root.setTag("forge-tabs-overview");
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(dp(12) + insets.getSystemWindowInsetLeft(), dp(8) + insets.getSystemWindowInsetTop(),
                dp(12) + insets.getSystemWindowInsetRight(), dp(8) + insets.getSystemWindowInsetBottom());
            return insets;
        });
        heading = new TextView(getContext());
        heading.setTextColor(Color.WHITE);
        heading.setTextSize(22);
        if (android.os.Build.VERSION.SDK_INT >= 28) heading.setAccessibilityHeading(true);
        root.addView(heading);
        LinearLayout modes = new LinearLayout(getContext());
        regular = button(modes, R.string.regular_tabs, "forge-tabs-regular", v -> changeMode(false));
        privateTabs = button(modes, R.string.private_tabs, "forge-tabs-private", v -> changeMode(true));
        root.addView(modes);
        search = new EditText(getContext());
        search.setTag("forge-tabs-search");
        search.setHint(R.string.search_tabs);
        search.setContentDescription(getContext().getString(R.string.search_tabs));
        search.setTextColor(Color.WHITE);
        search.setHintTextColor(Color.LTGRAY);
        search.setSingleLine(true);
        root.addView(search, new LinearLayout.LayoutParams(-1, dp(56)));
        ListView list = new ListView(getContext());
        list.setTag("forge-tabs-list");
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> {
            String tabId = visible.get(position).id;
            dismiss();
            host.select(tabId);
        });
        root.addView(list, new LinearLayout.LayoutParams(-1, 0, 1));
        TextView empty = new TextView(getContext());
        empty.setTag("forge-tabs-empty");
        empty.setText(R.string.no_matching_tabs);
        empty.setTextColor(Color.LTGRAY);
        root.addView(empty);
        list.setEmptyView(empty);
        LinearLayout actions = new LinearLayout(getContext());
        add = button(actions, R.string.new_tab, "forge-tabs-add", v -> { dismiss(); host.add(); });
        button(actions, R.string.done, "forge-tabs-done", v -> dismiss());
        root.addView(actions);
        LinearLayout privateActions = new LinearLayout(getContext());
        closePrivate = button(privateActions, R.string.close_private_tabs, "forge-tabs-close-private", v -> confirmClosePrivate());
        root.addView(privateActions);
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { refresh(); }
            @Override public void afterTextChanged(Editable s) {}
        });
        setContentView(root);
        root.setFocusableInTouchMode(true);
        root.requestFocus();
        refresh();
    }

    @Override protected void onStart() {
        super.onStart();
        getWindow().setLayout(-1, -1);
        refresh();
    }

    private void changeMode(boolean privateMode) {
        host.changeMode(privateMode);
        search.setText("");
        refresh();
    }

    private void confirmClosePrivate() {
        if (closeConfirmation != null) closeConfirmation.dismiss();
        AlertDialog confirm = new AlertDialog.Builder(getContext()).setTitle(R.string.close_private_tabs)
            .setMessage(R.string.close_private_warning)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.close_private_tabs, (dialog, which) -> {
                host.closePrivate(); search.setText(""); refresh();
            }).create();
        closeConfirmation = confirm;
        confirm.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        confirm.setOnShowListener(dialog -> confirm.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
        confirm.show();
    }

    @Override public void dismiss() {
        if (closeConfirmation != null) { closeConfirmation.dismiss(); closeConfirmation = null; }
        super.dismiss();
    }

    private void refresh() {
        if (search == null) return;
        boolean isPrivate = host.isPrivate();
        if (isPrivate) getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
        regular.setSelected(!isPrivate);
        privateTabs.setSelected(isPrivate);
        regular.setEnabled(isPrivate);
        privateTabs.setEnabled(!isPrivate);
        heading.setText(getContext().getString(isPrivate ? R.string.private_tab_count : R.string.tab_count,
            host.tabs().all().size()));
        String query = search.getText().toString().trim().toLowerCase(Locale.ROOT);
        visible.clear();
        for (BrowserTabs.Tab tab : host.tabs().all()) {
            if (query.isEmpty() || tab.title().toLowerCase(Locale.ROOT).contains(query)
                || tab.url().toLowerCase(Locale.ROOT).contains(query)) visible.add(tab);
        }
        add.setEnabled(host.tabs().all().size() < BrowserTabs.MAXIMUM_TABS);
        closePrivate.setVisibility(isPrivate ? View.VISIBLE : View.GONE);
        adapter.notifyDataSetChanged();
    }

    private final class TabAdapter extends BaseAdapter {
        @Override public int getCount() { return visible.size(); }
        @Override public BrowserTabs.Tab getItem(int position) { return visible.get(position); }
        @Override public long getItemId(int position) { return position; }
        @Override public View getView(int position, View convertView, ViewGroup parent) {
            BrowserTabs.Tab tab = getItem(position);
            String title = tab.title().isEmpty() ? (tab.url().equals("about:blank")
                ? getContext().getString(R.string.new_tab) : tab.url()) : tab.title();
            LinearLayout row = new LinearLayout(getContext());
            row.setTag("forge-tab-" + tab.id);
            row.setGravity(android.view.Gravity.CENTER_VERTICAL);
            row.setPadding(dp(8), dp(8), dp(8), dp(8));
            TextView label = new TextView(getContext());
            label.setTextColor(Color.WHITE);
            label.setTextSize(16);
            String displayTitle = tab.id.equals(host.tabs().selectedId())
                ? getContext().getString(R.string.selected_tab_title, title) : title;
            label.setText(getContext().getString(R.string.tab_overview_entry, displayTitle, tab.url()));
            label.setMaxLines(4);
            label.setFocusable(true);
            label.setOnClickListener(v -> { dismiss(); host.select(tab.id); });
            row.addView(label, new LinearLayout.LayoutParams(0, -2, 1));
            Button close = new Button(getContext());
            close.setText("×");
            close.setTag("forge-tab-close-" + tab.id);
            close.setContentDescription(getContext().getString(R.string.close_named_tab, title));
            close.setOnClickListener(v -> { host.close(tab.id); refresh(); });
            row.addView(close, new LinearLayout.LayoutParams(dp(52), dp(52)));
            return row;
        }
    }
}
