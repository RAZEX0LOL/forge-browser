/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import UIKit

enum BrowserPalette {
    static let background = UIColor(red: 0.025, green: 0.04, blue: 0.033, alpha: 1)
    static let surface = UIColor(red: 0.055, green: 0.08, blue: 0.065, alpha: 1)
    static let field = UIColor(red: 0.10, green: 0.14, blue: 0.12, alpha: 1)
    static let border = UIColor(red: 0.18, green: 0.24, blue: 0.20, alpha: 1)
    static let foreground = UIColor(red: 0.94, green: 0.97, blue: 0.95, alpha: 1)
    static let secondary = UIColor(red: 0.61, green: 0.69, blue: 0.65, alpha: 1)
    static let disabled = UIColor(red: 0.31, green: 0.39, blue: 0.35, alpha: 1)
    static let accent = UIColor(red: 0.64, green: 0.94, blue: 0.81, alpha: 1)
}

private final class ForgeMark: UIView {
    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        context.saveGState()
        context.scaleBy(x: bounds.width / 24, y: bounds.height / 24)
        BrowserPalette.accent.setFill()
        UIBezierPath(roundedRect: CGRect(x: 1, y: 1, width: 22, height: 22), cornerRadius: 6).fill()
        let path = UIBezierPath()
        path.move(to: CGPoint(x: 6, y: 19))
        for point in [CGPoint(x: 6, y: 5), CGPoint(x: 19, y: 5), CGPoint(x: 16, y: 9),
                      CGPoint(x: 10, y: 9), CGPoint(x: 10, y: 11), CGPoint(x: 16, y: 11),
                      CGPoint(x: 13, y: 15), CGPoint(x: 10, y: 15), CGPoint(x: 10, y: 19)] {
            path.addLine(to: point)
        }
        path.close()
        BrowserPalette.background.setFill()
        path.fill()
        context.restoreGState()
    }
}

final class BrowserStartView: UIView {
    private let headline = UILabel()
    private let subtitle = UILabel()
    private let primary = UIButton(type: .system)
    private let tabs = UIButton(type: .system)
    private let mark = ForgeMark()
    private let hero = UIStackView()
    private let footer = UILabel()
    private let provider = UILabel()
    private var markWidth: NSLayoutConstraint!
    private var markHeight: NSLayoutConstraint!
    private var heroTop: NSLayoutConstraint!
    private var headerTop: NSLayoutConstraint!
    private var footerGap: NSLayoutConstraint!
    private var footerBottom: NSLayoutConstraint!
    private var hiddenFooterHeight: NSLayoutConstraint!
    private var actionHeights: [NSLayoutConstraint] = []
    private var layoutMode = 0
    private var currentTab = BrowserTab()
    private var currentCount = 1
    private var restored = false
    var onSearch: (() -> Void)?
    var onTabs: (() -> Void)?
    var onRestore: (() -> Void)?

    private func text(_ key: String) -> String { NSLocalizedString(key, comment: "Forge start page") }

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = BrowserPalette.background
        accessibilityIdentifier = "forge-start"
        let scroll = UIScrollView()
        scroll.alwaysBounceVertical = true
        scroll.keyboardDismissMode = .interactive
        scroll.showsVerticalScrollIndicator = false
        let content = UIView()
        for view in [scroll, content] { view.translatesAutoresizingMaskIntoConstraints = false }
        addSubview(scroll)
        scroll.addSubview(content)
        NSLayoutConstraint.activate([
            scroll.leadingAnchor.constraint(equalTo: safeAreaLayoutGuide.leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: safeAreaLayoutGuide.trailingAnchor),
            scroll.topAnchor.constraint(equalTo: topAnchor), scroll.bottomAnchor.constraint(equalTo: bottomAnchor),
            content.leadingAnchor.constraint(equalTo: scroll.contentLayoutGuide.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: scroll.contentLayoutGuide.trailingAnchor),
            content.topAnchor.constraint(equalTo: scroll.contentLayoutGuide.topAnchor),
            content.bottomAnchor.constraint(equalTo: scroll.contentLayoutGuide.bottomAnchor),
            content.widthAnchor.constraint(equalTo: scroll.frameLayoutGuide.widthAnchor),
            content.heightAnchor.constraint(greaterThanOrEqualTo: scroll.frameLayoutGuide.heightAnchor)
        ])
        let fittingHeight = content.heightAnchor.constraint(equalTo: scroll.frameLayoutGuide.heightAnchor)
        fittingHeight.priority = UILayoutPriority(249)
        fittingHeight.isActive = true
        let brand = UILabel()
        brand.attributedText = NSAttributedString(string: "FORGE", attributes: [
            .font: UIFont.systemFont(ofSize: 16, weight: .bold), .kern: 4,
            .foregroundColor: BrowserPalette.foreground
        ])
        let preview = UILabel()
        preview.text = text("Early access")
        preview.font = .preferredFont(forTextStyle: .caption1)
        preview.adjustsFontForContentSizeCategory = true
        preview.textColor = BrowserPalette.secondary
        let header = UIStackView(arrangedSubviews: [brand, UIView(), preview])
        header.alignment = .center
        header.spacing = 16
        mark.backgroundColor = .clear
        mark.isAccessibilityElement = false
        markWidth = mark.widthAnchor.constraint(equalToConstant: 76)
        markHeight = mark.heightAnchor.constraint(equalToConstant: 76)
        markHeight.priority = UILayoutPriority(999)
        NSLayoutConstraint.activate([markWidth, markHeight])
        headline.font = UIFontMetrics(forTextStyle: .largeTitle).scaledFont(
            for: .systemFont(ofSize: 38, weight: .semibold), maximumPointSize: 52)
        headline.adjustsFontForContentSizeCategory = true
        headline.textColor = BrowserPalette.foreground
        headline.numberOfLines = 0
        headline.textAlignment = .center
        headline.accessibilityTraits = .header
        headline.accessibilityIdentifier = "forge-start-title"
        subtitle.font = .preferredFont(forTextStyle: .subheadline)
        subtitle.adjustsFontForContentSizeCategory = true
        subtitle.textColor = BrowserPalette.secondary
        subtitle.textAlignment = .center
        subtitle.numberOfLines = 0
        provider.text = text("Search with DuckDuckGo")
        provider.font = .preferredFont(forTextStyle: .caption1)
        provider.adjustsFontForContentSizeCategory = true
        provider.textColor = BrowserPalette.secondary
        provider.textAlignment = .center
        provider.numberOfLines = 0
        for button in [primary, tabs] {
            let height = button.heightAnchor.constraint(greaterThanOrEqualToConstant: 88)
            height.isActive = true
            actionHeights.append(height)
            button.layer.cornerRadius = 18
            button.layer.borderWidth = 1
            button.layer.borderColor = BrowserPalette.border.cgColor
            button.backgroundColor = BrowserPalette.surface
        }
        primary.accessibilityIdentifier = "forge-start-search"
        tabs.accessibilityIdentifier = "forge-start-tabs"
        primary.addAction(UIAction { [weak self] _ in
            guard let self = self else { return }
            if self.restored { self.onRestore?() } else { self.onSearch?() }
        }, for: .touchUpInside)
        tabs.addAction(UIAction { [weak self] _ in self?.onTabs?() }, for: .touchUpInside)
        let actions = UIStackView(arrangedSubviews: [primary, tabs])
        actions.distribution = .fillEqually
        actions.spacing = 12
        for element in [mark, headline, subtitle, provider, actions] { hero.addArrangedSubview(element) }
        hero.axis = .vertical
        hero.alignment = .center
        hero.spacing = 18
        hero.setCustomSpacing(26, after: mark)
        hero.setCustomSpacing(10, after: headline)
        hero.setCustomSpacing(26, after: provider)
        actions.widthAnchor.constraint(equalTo: hero.widthAnchor).isActive = true
        footer.text = text("Built on WebKit. HTTPS only. An early mobile build.")
        footer.font = .preferredFont(forTextStyle: .caption1)
        footer.adjustsFontForContentSizeCategory = true
        footer.textColor = BrowserPalette.secondary
        footer.textAlignment = .center
        footer.numberOfLines = 0
        for view in [header, hero, footer] {
            view.translatesAutoresizingMaskIntoConstraints = false
            content.addSubview(view)
            view.centerXAnchor.constraint(equalTo: content.centerXAnchor).isActive = true
            view.leadingAnchor.constraint(greaterThanOrEqualTo: content.leadingAnchor, constant: 28).isActive = true
            view.trailingAnchor.constraint(lessThanOrEqualTo: content.trailingAnchor, constant: -28).isActive = true
            view.widthAnchor.constraint(lessThanOrEqualToConstant: 420).isActive = true
            let width = view.widthAnchor.constraint(equalTo: content.widthAnchor, constant: -56)
            width.priority = .defaultHigh
            width.isActive = true
        }
        let centered = hero.centerYAnchor.constraint(equalTo: content.centerYAnchor, constant: -4)
        centered.priority = .defaultHigh
        headerTop = header.topAnchor.constraint(equalTo: content.topAnchor, constant: 22)
        heroTop = hero.topAnchor.constraint(greaterThanOrEqualTo: header.bottomAnchor, constant: 36)
        footerGap = footer.topAnchor.constraint(greaterThanOrEqualTo: hero.bottomAnchor, constant: 32)
        footerBottom = footer.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -22)
        hiddenFooterHeight = footer.heightAnchor.constraint(equalToConstant: 0)
        NSLayoutConstraint.activate([
            headerTop, heroTop, centered, footerGap, footerBottom
        ])
        configure(tab: BrowserTab(), count: 1)
    }

    required init?(coder: NSCoder) { return nil }

    override func layoutSubviews() {
        super.layoutSubviews()
        guard bounds.height > 0 else { return }
        let mode = bounds.height < 360 ? 2 : bounds.height < 560 ? 1 : 0
        guard mode != layoutMode else { return }
        layoutMode = mode
        mark.isHidden = mode == 2
        provider.isHidden = mode == 2
        footer.isHidden = mode == 2
        hiddenFooterHeight.isActive = mode == 2
        markWidth.constant = mode == 0 ? 76 : 52
        markHeight.constant = mode == 0 ? 76 : 52
        headerTop.constant = mode == 0 ? 22 : 14
        heroTop.constant = mode == 0 ? 36 : mode == 1 ? 24 : 16
        footerGap.constant = mode == 0 ? 32 : mode == 1 ? 20 : 14
        footerBottom.constant = mode == 0 ? -22 : -14
        hero.spacing = mode == 0 ? 18 : 12
        hero.setCustomSpacing(mode == 0 ? 26 : 18, after: mark)
        hero.setCustomSpacing(mode == 0 ? 10 : 8, after: headline)
        hero.setCustomSpacing(mode == 0 ? 26 : 18, after: provider)
        for height in actionHeights { height.constant = mode == 0 ? 88 : mode == 1 ? 76 : 56 }
        headline.font = UIFontMetrics(forTextStyle: .largeTitle).scaledFont(
            for: .systemFont(ofSize: mode == 0 ? 38 : mode == 1 ? 30 : 26, weight: .semibold), maximumPointSize: 52)
        configure(tab: currentTab, count: currentCount)
    }

    func configure(tab: BrowserTab, count: Int) {
        currentTab = tab
        currentCount = count
        restored = tab.url != "about:blank"
        let title = restored ? text("Your tab is saved.") : text("The web.\nYour way.")
        headline.text = layoutMode == 2 ? title.replacingOccurrences(of: "\n", with: " ") : title
        subtitle.text = restored
            ? String(format: text("%@ will load only when you choose."), URL(string: tab.url)?.host ?? tab.url)
            : text("Enter an address or discover something new.")
        var first = UIButton.Configuration.plain()
        first.image = UIImage(systemName: restored ? "arrow.down.circle" : "magnifyingglass")
        first.preferredSymbolConfigurationForImage = UIImage.SymbolConfiguration(pointSize: 21, weight: .medium)
        first.imagePlacement = layoutMode == 2 ? .leading : .top
        first.imagePadding = layoutMode == 2 ? 8 : 10
        first.baseForegroundColor = BrowserPalette.accent
        var titleAttributes = AttributeContainer()
        titleAttributes.font = UIFont.preferredFont(forTextStyle: .subheadline)
        titleAttributes.foregroundColor = BrowserPalette.foreground
        first.attributedTitle = AttributedString(text(restored ? "Load page" : "Search the web"), attributes: titleAttributes)
        first.contentInsets = layoutMode == 2
            ? NSDirectionalEdgeInsets(top: 10, leading: 12, bottom: 10, trailing: 12)
            : NSDirectionalEdgeInsets(top: 14, leading: 8, bottom: 14, trailing: 8)
        primary.configuration = first
        var second = first
        second.image = UIImage(systemName: "square.on.square")
        second.attributedTitle = AttributedString(String(format: text("Tabs (%ld)"), count), attributes: titleAttributes)
        tabs.configuration = second
    }
}
