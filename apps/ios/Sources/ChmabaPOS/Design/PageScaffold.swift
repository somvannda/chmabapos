import SwiftUI

// The shared screen vocabulary, ported from apps/android/prototype/mobile-ui.html.
//
// Every non-POS screen in the prototype is the same shape:
//
//   .appbar   sticky, bg #f7f7fa, padding 12/16, title 20px 800 -0.05em, sub 11px muted
//   .pad      padding 16
//   .card     surface, 1px #e9e9ef, radius 16, padding 16
//   .list     surface, 1px border, radius 16, rows padding 13/16 divided by #f2f2f5
//   .stat     radius 16, padding 14
//
// Building them once here is what stops 30 screens drifting apart.

/// The scrolling body of a screen: `#f7f7fa`, 16pt padding.
struct PageBody<Content: View>: View {
    var topPadding: CGFloat = 16
    @ViewBuilder var content: () -> Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                content()
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16)
            .padding(.top, topPadding)
            .padding(.bottom, 20)
        }
        .background(ChmabaColor.background)
    }
}

/// `.appbar` — the sticky header above the scrolling body.
///
/// The prototype's border-bottom is `1px solid transparent` and only becomes visible
/// once the content scrolls (`--border`). Drawing it unconditionally was putting a line
/// under every page title that the prototype does not show.
struct AppBar<Content: View>: View {
    var scrolled: Bool = false
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(spacing: 0) {
            content()
            Rectangle()
                .fill(scrolled ? ChmabaColor.border : .clear)
                .frame(height: 1)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(ChmabaColor.background)
    }
}

/// `.abrow` — the icon / title / actions row inside an app bar.
struct AppBarRow<Leading: View, Trailing: View>: View {
    @ViewBuilder var leading: () -> Leading
    @ViewBuilder var trailing: () -> Trailing
    let title: String
    let subtitle: String?
    /// Shows the green "open" dot before the subtitle, as the prototype does.
    var live: Bool = false

    var body: some View {
        HStack(spacing: 10) {
            leading()

            VStack(alignment: .leading, spacing: 2) {
                if let subtitle {
                    HStack(spacing: 6) {
                        if live { Circle().fill(BadgeTone.green.dot).frame(width: 6, height: 6) }
                        Text(subtitle)
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundStyle(ChmabaColor.muted)
                    }
                }
                Text(title)
                    .font(.system(size: 19, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            trailing()
        }
    }
}

/// `.iconbtn` — 34pt square, radius 10, hairline border.
struct IconButton: View {
    let symbol: String
    var plain: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 15))
                .foregroundStyle(ChmabaColor.textSecondary)
                .frame(width: 34, height: 34)
        }
        .buttonStyle(.plain)
        .background(plain ? .clear : ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 10))
        .overlay {
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(plain ? .clear : ChmabaColor.border, lineWidth: 1)
        }
    }
}

/// `.sec-title` and `.sec-sub` pair.
struct SectionHeading: View {
    let title: String
    var subtitle: String?
    var trailing: AnyView?

    var body: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 13, weight: .heavy))
                    .tracking(-0.025)
                    .foregroundStyle(ChmabaColor.textPrimary)
                if let subtitle {
                    Text(subtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(Color(hex: 0x999AA4))
                        .padding(.bottom, 10)
                }
            }
            Spacer()
            if let trailing { trailing }
        }
    }
}

/// `.card` — a surface panel. `padding: 0` plus clipping gives `.card.p0`.
struct POSPanel<Content: View>: View {
    var padding: CGFloat = 16
    var soft: Bool = false
    var dark: Bool = false
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(padding)
        .background(
            dark ? ChmabaColor.inkStrong : (soft ? ChmabaColor.backgroundAlt : ChmabaColor.surface),
            in: RoundedRectangle(cornerRadius: 16)
        )
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(dark ? ChmabaColor.inkStrong : ChmabaColor.border, lineWidth: 1)
        }
    }
}

/// `.list` — a bordered panel whose rows supply their own padding and dividers.
struct PanelList<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            content()
        }
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(ChmabaColor.border, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

/// `.lrow` — padding 13/16, gap 11, divided by a 1px `#f2f2f5` rule.
struct ListRow<Trailing: View>: View {
    var showsDivider: Bool = true
    @ViewBuilder var content: () -> AnyView
    @ViewBuilder var trailing: () -> Trailing
    var action: (() -> Void)?

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 11) {
                content()
                Spacer(minLength: 0)
                trailing()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 13)
            .contentShape(Rectangle())
            .onTapGesture { action?() }

            if showsDivider {
                Rectangle().fill(Color(hex: 0xF2F2F5)).frame(height: 1)
            }
        }
    }
}

/// The 34pt rounded colour chip — `.mark`, used for product/category initials.
struct MarkChip: View {
    let text: String
    var background: Color = ChmabaColor.grey300
    var symbol: String?

    var body: some View {
        RoundedRectangle(cornerRadius: 11, style: .continuous)
            .fill(background)
            .frame(width: 34, height: 34)
            .overlay {
                if let symbol {
                    Image(systemName: symbol).font(.system(size: 15)).foregroundStyle(Color(hex: 0x343039))
                } else {
                    Text(text)
                        .font(.system(size: 10, weight: .heavy))
                        .foregroundStyle(Color(hex: 0x343039))
                }
            }
    }
}

/// `.stat` — tone background, radius 16, padding 14.
///
/// The compact variant is the prototype's `.stat` with inline overrides: padding 10,
/// label 8px, value 17px. Used by the three-up summary rows on Products/Categories/
/// Inventory/Purchasing, which are narrower than the Dashboard's two-up grid.
struct StatTile: View {
    let label: String
    let value: String
    var detail: String?
    var tone: BadgeTone = .violet
    var compact: Bool = false
    /// Substitutes the plain `--bg-alt` panel for a tone; Categories uses this for
    /// its third tile.
    var neutralPanel: Bool = false

    private var background: Color {
        neutralPanel ? ChmabaColor.backgroundAlt : tone.background
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(label)
                .font(.system(size: compact ? 8 : 9, weight: .bold))
                .tracking(compact ? 0.8 : 0.9)
                .textCase(.uppercase)
                .foregroundStyle(ChmabaColor.muted)
                .lineLimit(1)
                .minimumScaleFactor(0.7)

            Text(value)
                .font(.system(size: compact ? 17 : 20, weight: .heavy))
                .tracking(compact ? -0.85 : -1)
                .foregroundStyle(ChmabaColor.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .padding(.top, compact ? 3 : 5)
                .padding(.bottom, detail == nil ? 0 : (compact ? 0 : 2))

            if let detail {
                Text(detail)
                    .font(.system(size: 9))
                    .foregroundStyle(ChmabaColor.faint)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(compact ? 10 : 14)
        .background(background, in: RoundedRectangle(cornerRadius: 16))
        .overlay {
            if neutralPanel {
                RoundedRectangle(cornerRadius: 16).strokeBorder(ChmabaColor.border, lineWidth: 1)
            }
        }
    }
}

/// The metric grid. `columns: 2` matches `.grid4` on mobile; `columns: 3` matches
/// `.grid3` (gap 9), used by the compact summary rows on Products, Categories,
/// Inventory and Purchasing.
struct StatGrid<Content: View>: View {
    var columns: Int = 2
    @ViewBuilder var content: () -> Content

    var body: some View {
        let gap: CGFloat = columns >= 3 ? 9 : 10
        LazyVGrid(
            columns: Array(repeating: GridItem(.flexible(), spacing: gap), count: columns),
            spacing: gap
        ) {
            content()
        }
    }
}

/// `.track` — a 6pt rail with a `#b9b2fa` fill.
struct ProgressTrack: View {
    /// 0...1
    let fraction: Double

    var body: some View {
        GeometryReader { proxy in
            ZStack(alignment: .leading) {
                Capsule().fill(Color(hex: 0xF0F0F4))
                Capsule().fill(Color(hex: 0xB9B2FA))
                    .frame(width: max(0, min(1, fraction)) * proxy.size.width)
            }
        }
        .frame(height: 6)
    }
}

/// The chip row used for filters and segments (`.chips` / `.chip` / `.chip.seg`).
struct ChipRow<T: Hashable>: View {
    let items: [T]
    let title: (T) -> String
    @Binding var selection: T
    var segmented: Bool = true

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 7) {
                ForEach(items, id: \.self) { item in
                    let isOn = item == selection
                    Button {
                        selection = item
                    } label: {
                        Text(title(item))
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(isOn ? .white : ChmabaColor.textSecondary)
                            .padding(.horizontal, 13)
                            .frame(height: 32)
                            .background(
                                isOn ? ChmabaColor.purple : ChmabaColor.surface,
                                in: RoundedRectangle(cornerRadius: segmented ? 9 : 99)
                            )
                            .overlay {
                                RoundedRectangle(cornerRadius: segmented ? 9 : 99)
                                    .strokeBorder(
                                        isOn ? ChmabaColor.purple : ChmabaColor.outline,
                                        lineWidth: 1
                                    )
                            }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.vertical, 2)
        }
    }
}

/// `.bnav` — the bottom navigation bar.
///
/// Height 64, 1pt top border, and per the prototype's enhanced rules each item is:
///   - a 40x26 radius-11 pill behind the icon, lavender when active and shifted up 1pt
///   - a 30x3 radius-bottom purple indicator bar at the very top when active
///   - icon 20pt, label 9pt (800 when active, 700 otherwise)
///   - the icon scales to 0.9 while pressed
struct BottomNav: View {
    @Binding var tab: MainTab

    var body: some View {
        HStack(spacing: 0) {
            ForEach(MainTab.allCases, id: \.self) { item in
                let isOn = tab == item
                Button {
                    tab = item
                } label: {
                    VStack(spacing: 3) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 11, style: .continuous)
                                .fill(isOn ? ChmabaColor.lavender : .clear)
                                .frame(width: 40, height: 26)
                            Image(systemName: item.symbol)
                                .font(.system(size: 20))
                                .foregroundStyle(isOn ? ChmabaColor.purple : ChmabaColor.faint)
                        }
                        .offset(y: isOn ? -1 : 0)

                        Text(item.title)
                            .font(.system(size: 9, weight: isOn ? .heavy : .bold))
                            .foregroundStyle(isOn ? ChmabaColor.purple : ChmabaColor.faint)
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 64)
                    .contentShape(Rectangle())
                }
                .buttonStyle(ChmabaPressStyle(scale: 0.94))
                .overlay(alignment: .top) {
                    RoundedRectangle(cornerRadius: 2, style: .continuous)
                        .fill(ChmabaColor.purple)
                        .frame(width: 30, height: 3)
                        .scaleEffect(x: isOn ? 1 : 0, anchor: .center)
                        .animation(.easeOut(duration: 0.24), value: isOn)
                }
            }
        }
        .frame(height: 64)
        .background(ChmabaColor.surface)
        .overlay(alignment: .top) {
            Rectangle().fill(ChmabaColor.border).frame(height: 1)
        }
    }
}

/// The four bottom-nav destinations. Labels are the prototype's own.
enum MainTab: String, CaseIterable, Hashable {
    case home, pos, orders, more

    var title: String {
        switch self {
        case .home: return "Home"
        case .pos: return "POS"
        case .orders: return "Orders"
        case .more: return "More"
        }
    }

    /// SF Symbols stand in until the Lucide set is ported. SCREENS.md is explicit
    /// that the icon set must not change, so this is a known gap, not a choice.
    var symbol: String {
        switch self {
        case .home: return "house"
        case .pos: return "cart"
        case .orders: return "doc.text"
        case .more: return "slider.horizontal.3"
        }
    }
}

/// The 42pt square action button in the prototype's POS header.
///
/// 42pt, radius 13, white with a hairline border, icon 19pt in gray700, and an
/// optional count badge at the top-trailing corner for held orders.
struct SquareIconButton: View {
    let symbol: String
    let help: String
    var badge: String?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 19))
                .foregroundStyle(ChmabaColor.grey700)
                .frame(width: 42, height: 42)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 13))
                .overlay {
                    RoundedRectangle(cornerRadius: 13)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
                .overlay(alignment: .topTrailing) {
                    if let badge {
                        Text(badge)
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(.white)
                            .frame(minWidth: 16, minHeight: 16)
                            .background(ChmabaColor.purple, in: Circle())
                            .offset(x: 5, y: -5)
                    }
                }
        }
        .buttonStyle(ChmabaPressStyle(scale: 0.9))
        .accessibilityLabel(help)
    }
}

/// A small icon button that cycles the app appearance, for the header corner.
///
/// Shows the CURRENT mode and advances on tap (Light -> Dark -> System -> Light). A
/// segmented control was doing this in the More list, but a control you have to hunt
/// for is not much of a control, and the prototype keeps theme switching in Settings
/// which is still a placeholder here.
struct AppearanceToggleButton: View {
    @AppStorage(AppAppearance.storageKey) private var raw = AppAppearance.light.rawValue

    private var current: AppAppearance { AppAppearance(rawValue: raw) ?? .light }

    var body: some View {
        Button {
            let all = AppAppearance.allCases
            let index = all.firstIndex(of: current) ?? 0
            raw = all[(index + 1) % all.count].rawValue
        } label: {
            Image(systemName: current.symbol)
                .font(.system(size: 15))
                .foregroundStyle(ChmabaColor.textSecondary)
                .frame(width: 34, height: 34)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 10))
                .overlay {
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
        }
        .buttonStyle(ChmabaPressStyle(scale: 0.9))
        .accessibilityLabel("Appearance")
        .accessibilityValue(current.title)
        .accessibilityHint("Switches between light, dark and system")
    }
}
