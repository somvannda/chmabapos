import SwiftUI

// Shared components mirroring apps/android/.../ui/components/.
//
// These are ports, not reinterpretations: same variants, same sizes, same radii,
// same colours. Two clients of one product should be indistinguishable at a glance,
// so where Android made a choice we keep it rather than "improving" it here.

// MARK: - Logo

/// The chmaba brand mark, loaded from the rendered brand SVGs.
///
/// The artwork is NOT redrawn here. `apps/web/public/favicon-dark.svg` (the lime
/// chip) and `logo_text.svg` (the lockup) are rasterised at build-prep time by
/// `scripts/75-render-brand-assets.sh` and shipped as SwiftPM resources, because
/// iOS cannot load SVG at runtime.
///
/// Two details that make this the real asset rather than a lookalike:
///   - the wordmark is CUSTOM VECTOR GLYPHS, not a font, so `Text("chmaba")` could
///     never match it -- it has to come from the SVG
///   - `logo_text.svg` ships the dark chip with white rings; the lime variant used
///     here is the same file with only the chip fill and ring stroke swapped, which
///     is exactly what the Android client does
struct ChmabaLogo: View {
    var chipSize: CGFloat = 32
    var wordmark: Bool = true
    /// Use the white-wordmark variant, for a dark hero.
    var onDark: Bool = false

    /// `logo_text.svg` has a 231.34 x 68 viewBox with a 64-unit chip, so the lockup
    /// is 68/64 of the chip height and 3.402x wider than it is tall. Deriving the
    /// frame this way keeps the lockup in proportion at any chip size.
    private var lockupHeight: CGFloat { chipSize * 68 / 64 }
    private var lockupWidth: CGFloat { lockupHeight * 231.34 / 68 }

    var body: some View {
        if wordmark {
            brandImage(onDark ? "chmaba-wordmark-dark" : "chmaba-wordmark")
                .resizable()
                .interpolation(.high)
                .scaledToFit()
                .frame(width: lockupWidth, height: lockupHeight)
                .accessibilityLabel("Chmaba")
        } else {
            brandImage("chmaba-mark")
                .resizable()
                .interpolation(.high)
                .scaledToFit()
                .frame(width: chipSize, height: chipSize)
                .accessibilityLabel("Chmaba")
        }
    }
}

/// Loads a bundled brand PNG.
///
/// Not `private`: the auth scaffold needs it for the Google mark too.
///
/// SwiftPM's `copy` rule preserves the path relative to the target directory while
/// `process` flattens it, and which one applies is not something to guess at -- so
/// both layouts are tried and the first hit wins.
func brandImage(_ name: String) -> Image {
    let bundle = Bundle.module
    let candidates: [URL?] = [
        bundle.url(forResource: name, withExtension: "png"),
        bundle.url(forResource: name, withExtension: "png", subdirectory: "Resources"),
    ]
    for case let url? in candidates {
        if let data = try? Data(contentsOf: url), let image = UIImage(data: data) {
            return Image(uiImage: image)
        }
    }
    // A missing asset should be visible, not silent -- but it must not crash a till.
    return Image(systemName: "questionmark.square.dashed")
}

// MARK: - Press feedback

/// Press feedback for the custom buttons.
///
/// `.buttonStyle(.plain)` strips the default highlight, so every button built here
/// was giving NO response to a tap. On a slow network call that reads as a dead
/// button, which is exactly how it was reported. 0.97/0.85 is deliberately subtle --
/// enough to register, not enough to look bouncy in a till.
struct ChmabaPressStyle: ButtonStyle {
    var scale: CGFloat = 0.97

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? scale : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

// MARK: - Button

enum ChmabaButtonVariant {
    case primary, outline, soft, ghost, danger, lime
}

enum ChmabaButtonSize {
    case small, medium, large

    var height: CGFloat {
        switch self {
        case .small: return 36
        case .medium: return 40
        case .large: return 48
        }
    }

    var fontSize: CGFloat {
        switch self {
        case .small: return 12
        case .medium, .large: return 14
        }
    }
}

/// Ported from `ChmabaButton.kt`.
struct ChmabaButton: View {
    let text: String
    var variant: ChmabaButtonVariant = .primary
    var size: ChmabaButtonSize = .medium
    var enabled: Bool = true
    var fullWidth: Bool = false
    var loading: Bool = false
    var leadingIcon: ChmabaIcon?
    var trailingIcon: ChmabaIcon?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if loading {
                    ProgressView().tint(foreground)
                } else if let leadingIcon {
                    // `.btn .ic` is 15x15 in the prototype.
                    ChmabaIconView(icon: leadingIcon, size: 15, color: foreground)
                }
                Text(text)
                    .font(.system(size: size.fontSize, weight: .semibold))
                if let trailingIcon {
                    ChmabaIconView(icon: trailingIcon, size: 15, color: foreground)
                }
            }
            .frame(maxWidth: fullWidth ? .infinity : nil)
            .frame(height: size.height)
            .padding(.horizontal, 16)
            // Without this the hit area is only the opaque subviews, so taps in the
            // gaps between the icon, label and edges fall through. That is the other
            // half of "I have to tap a few times".
            .contentShape(Rectangle())
        }
        .buttonStyle(ChmabaPressStyle())
        .foregroundStyle(foreground)
        .background(background, in: RoundedRectangle(cornerRadius: 12))
        .overlay {
            if variant == .outline {
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(Color(hex: 0xDEDEE7), lineWidth: 1)
            }
        }
        .opacity(enabled ? 1 : 0.5)
        .disabled(!enabled || loading)
    }

    private var background: Color {
        switch variant {
        case .primary: return ChmabaColor.purple
        case .outline: return .white
        case .soft: return ChmabaColor.lavender
        case .ghost: return .clear
        case .danger: return Color(hex: 0xFFF0EE)
        case .lime: return ChmabaColor.lime
        }
    }

    private var foreground: Color {
        switch variant {
        case .primary: return .white
        case .outline: return ChmabaColor.grey900
        case .soft: return ChmabaColor.violet
        case .ghost: return ChmabaColor.grey600
        case .danger: return ChmabaColor.danger
        case .lime: return Color(hex: 0x1B2715)
        }
    }
}

// MARK: - Badge

/// Ported from `ChmabaBadge.kt`: radius 6, 8/4 padding, 6pt dot, 11pt SemiBold.
struct ChmabaBadge: View {
    let text: String
    var tone: BadgeTone = .neutral
    var showDot: Bool = false

    var body: some View {
        HStack(spacing: 6) {
            if showDot {
                RoundedRectangle(cornerRadius: 3)
                    .fill(tone.dot)
                    .frame(width: 6, height: 6)
            }
            Text(text)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(tone.foreground)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(tone.background, in: RoundedRectangle(cornerRadius: 6))
    }
}

/// Ported from `StatusBadge` in apps/android.
struct StatusBadge: View {
    let status: OrderStatus

    var body: some View {
        ChmabaBadge(text: status.label, tone: status.tone, showDot: true)
    }
}

// MARK: - Cards

/// Ported from `StatCard`: radius 16, tone background, 16 padding.
struct StatCard: View {
    let label: String
    let value: String
    var caption: String?
    var tone: BadgeTone = .neutral

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(ChmabaColor.textSecondary)
            Text(value)
                .font(.system(size: 22, weight: .heavy))
                .foregroundStyle(ChmabaColor.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            if let caption {
                Text(caption)
                    .font(.system(size: 10))
                    .foregroundStyle(ChmabaColor.grey500)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(tone.background, in: RoundedRectangle(cornerRadius: 16))
    }
}

/// `.pcard` — the product tile, from the prototype's POS grid.
///
/// Mobile values (the prototype overrides the desktop ones):
///   .pgrid  gap 9, two columns
///   .pcard  surface, 1px border, radius 12, overflow hidden, press scale 0.985
///   .pimg   height 58, initials 14px/800 #343039, darkening gradient at the bottom
///   .pbody  padding 8/9/9
///   .pname  11px/700 #303139, line-height 1.25, max two lines
///   .pprice 12.5px/800, letter-spacing -.03em, 2pt above
///   .pmeta  9.5px faint -- the stock line is TEXT, not a badge
///
/// An earlier version of this was 140x180 with a 100pt header, 13px text and overlay
/// pills. None of that is in the prototype.
struct ProductCard: View {
    let product: ProductRead
    var tint: Color = ChmabaColor.purple
    let onTap: () -> Void

    private var isOutOfStock: Bool { product.trackInventory && product.onHand <= 0 }
    private var isLow: Bool {
        product.trackInventory && product.onHand > 0
            && product.onHand <= Double(product.reorderPoint)
    }

    /// `.pmeta` tone: faint normally, warning when low, danger when out.
    private var metaColour: Color {
        if isOutOfStock { return BadgeTone.red.foreground }
        if isLow { return BadgeTone.yellow.foreground }
        return ChmabaColor.faint
    }

    private var metaText: String? {
        guard product.trackInventory else { return nil }
        if isOutOfStock { return "Out of stock" }
        if isLow { return "\(Int(product.onHand)) left" }
        return "\(Int(product.onHand)) in stock"
    }

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: 0) {
                ZStack {
                    Rectangle().fill(tint)
                    Text(initials)
                        .font(.system(size: 14, weight: .heavy))
                        .foregroundStyle(Color(hex: 0x343039))
                }
                .frame(height: 58)
                .overlay {
                    // .pimg::after -- linear-gradient(180deg, transparent 55%, rgba(0,0,0,.06))
                    LinearGradient(
                        stops: [
                            .init(color: .clear, location: 0.55),
                            .init(color: .black.opacity(0.06), location: 1),
                        ],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                }

                VStack(alignment: .leading, spacing: 0) {
                    Text(product.name)
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(Color(hex: 0x303139))
                        .lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Text(money(product.price.value))
                        .font(.system(size: 12.5, weight: .heavy))
                        .tracking(-0.39)
                        .foregroundStyle(ChmabaColor.textPrimary)
                        .padding(.top, 2)
                    if let metaText {
                        Text(metaText)
                            .font(.system(size: 9.5))
                            .foregroundStyle(metaColour)
                            .padding(.top, 1)
                    }
                }
                .padding(.horizontal, 9)
                .padding(.top, 8)
                .padding(.bottom, 9)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .background(ChmabaColor.surface)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay {
                RoundedRectangle(cornerRadius: 12).strokeBorder(ChmabaColor.border, lineWidth: 1)
            }
            .opacity(isOutOfStock ? 0.5 : 1)
        }
        .buttonStyle(ChmabaPressStyle(scale: 0.985))
        .disabled(isOutOfStock)
    }

    private var initials: String {
        product.name.split(separator: " ").prefix(2)
            .compactMap { $0.first.map(String.init) }
            .joined()
            .uppercased()
    }
}

// MARK: - Fields

/// Ported from `ChmabaTextField`: label 12pt SemiBold grey700, 6pt gap,
/// 44pt field, radius 12, grey300 border.
struct ChmabaField<Content: View>: View {
    let label: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(ChmabaColor.grey700)
            content()
                .textFieldStyle(.plain)
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12).strokeBorder(ChmabaColor.outline, lineWidth: 1)
                }
        }
    }
}

/// Ported from `ChmabaSearchBar`: 44pt, radius 12, grey400 icon, clear button.
struct ChmabaSearchBar: View {
    let placeholder: String
    @Binding var text: String

    var body: some View {
        HStack(spacing: 8) {
            ChmabaIconView(icon: .search, size: 15, color: ChmabaColor.grey400)

            TextField(placeholder, text: $text)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.search)

            if !text.isEmpty {
                Button {
                    text = ""
                } label: {
                    ChmabaIconView(icon: .close, size: 15, color: ChmabaColor.grey400)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 12)
        .frame(height: 44)
        .background(ChmabaColor.surfaceVariant, in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Load state

/// Ported from `LoadStateNotice`: one place for loading / failed-with-retry, so
/// screens do not each invent their own error presentation.
struct LoadStateNotice: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            ChmabaIconView(icon: .alert, size: 32, color: BadgeTone.red.foreground)
            Text(message)
                .font(.system(size: 13))
                .multilineTextAlignment(.center)
                .foregroundStyle(ChmabaColor.textSecondary)
                .padding(.horizontal, 24)
            ChmabaButton(text: "Try again", variant: .soft, size: .small, action: onRetry)
        }
    }
}
