import SwiftUI

/// Colour and type tokens mirrored from `apps/android/DESIGN_GUIDE.md`.
///
/// The Android client is the reference implementation of this design system
/// (itself a ~95% match to the web POS). Keeping the same values here means the
/// iOS app is recognisably the same product, and the guide remains the single
/// source of truth for both.
///
/// When the guide changes, change it here too -- do not invent new values.

extension Color {
    /// 0xRRGGBB -> Color
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255.0,
            green: Double((hex >> 8) & 0xFF) / 255.0,
            blue: Double(hex & 0xFF) / 255.0,
            opacity: 1.0
        )
    }

    /// Builds a light/dark pair so the app follows the system appearance.
    static func adaptive(light: UInt32, dark: UInt32) -> Color {
        Color(UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(Color(hex: dark))
                : UIColor(Color(hex: light))
        })
    }
}

enum ChmabaColor {
    // Primary
    static let purple = Color(hex: 0x6957F5)
    static let lime = Color(hex: 0xC4F27C)

    // Status
    static let success = Color(hex: 0x4CAF50)
    static let danger = Color(hex: 0xF44336)
    static let warning = Color(hex: 0xFF9800)
    static let warningYellow = Color(hex: 0xFFB300)

    // Grey ramp (100 -> 900)
    static let grey100 = Color(hex: 0xF5F5F7)
    static let grey200 = Color(hex: 0xE9E9EF)
    static let grey300 = Color(hex: 0xDFDFE8)
    static let grey400 = Color(hex: 0xB0B1BA)
    static let grey500 = Color(hex: 0x92939D)
    static let grey600 = Color(hex: 0x6F707A)
    static let grey700 = Color(hex: 0x4F5059)
    static let grey800 = Color(hex: 0x303139)
    static let grey900 = Color(hex: 0x202128)

    // Accents
    static let lavender = Color(hex: 0xF0EFFF)
    static let peach = Color(hex: 0xFFF1E9)
    static let limeLight = Color(hex: 0xEFF9E6)
    static let violet = Color(hex: 0x6555DF)

    // Web/prototype tokens. SCREENS.md says these are "lifted from web" and "must
    // match exactly" -- and they are NOT all the same as the Android greys. The
    // prototype's muted/faint sit a step darker than gray500/gray400 (898a95 vs
    // 92939d, a1a2ab vs b0b1ba). Both sets are kept so a screen can use whichever
    // its own design actually specifies, rather than one silently overriding.
    static let inkStrong = Color(hex: 0x17181C)
    static let muted = Color(hex: 0x898A95)
    static let faint = Color(hex: 0xA1A2AB)
    static let ghost = Color(hex: 0xB0B1BA)
    static let backgroundAlt = Color.adaptive(light: 0xFAFAFD, dark: 0x15161A)
    static let border = Color.adaptive(light: 0xE9E9EF, dark: 0x2A2B30)
    static let borderStrong = Color.adaptive(light: 0xDEDEE7, dark: 0x3A3B42)
    /// Input focus ring, from the prototype's `:focus` rule (border #887bf3 plus a
    /// 4pt rgba(105,87,245,.1) glow).
    static let focusRing = Color(hex: 0x887BF3)

    // Surfaces -- tokens and values mirror ui/theme/Color.kt in apps/android.
    // NOTE: ChmabaBlue in that file is 0xFF6957F5, i.e. the brand purple; the name
    // is legacy. Kept as `purple` here because that is what it actually is.
    //
    // ChmabaBackground is #F7F7FA, deliberately NOT white -- white is the surface,
    // and the subtle difference is what gives cards their edge.
    static let background = Color.adaptive(light: 0xF7F7FA, dark: 0x111114)
    static let surface = Color.adaptive(light: 0xFFFFFF, dark: 0x1A1B20)
    static let surfaceVariant = Color.adaptive(light: 0xF5F5F7, dark: 0x2A2B30)
    static let outline = Color.adaptive(light: 0xDFDFE8, dark: 0x363740)
    static let textPrimary = Color.adaptive(light: 0x202128, dark: 0xE4E4E8)
    static let textSecondary = Color.adaptive(light: 0x4F5059, dark: 0xB0B1BA)
}

/// Badge tones, mirroring `BadgeTone` in apps/android/.../ChmabaBadge.kt.
///
/// Android uses colour names (Green/Yellow/Red/Violet/Blue), not semantic ones, so
/// the same names are kept here -- inventing a second vocabulary is how two clients
/// drift apart.
enum BadgeTone {
    case neutral, green, yellow, red, violet, blue

    var background: Color {
        switch self {
        case .neutral: return Color(hex: 0xF1F1F5)
        case .green: return Color(hex: 0xEDF9E4)
        case .yellow: return Color(hex: 0xFFF6DF)
        case .red: return Color(hex: 0xFFF0EE)
        case .violet: return ChmabaColor.lavender
        case .blue: return Color(hex: 0xEAF4FF)
        }
    }

    var foreground: Color {
        switch self {
        case .neutral: return Color(hex: 0x686974)
        case .green: return Color(hex: 0x4F8B32)
        case .yellow: return Color(hex: 0xAD7D1C)
        case .red: return Color(hex: 0xC2564B)
        case .violet: return Color(hex: 0x6555DF)
        case .blue: return Color(hex: 0x3579B8)
        }
    }

    /// The status dot, where one is shown.
    var dot: Color {
        switch self {
        case .neutral: return Color(hex: 0x9899A4)
        case .green: return Color(hex: 0x77BB4B)
        case .yellow: return Color(hex: 0xDCA93C)
        case .red: return Color(hex: 0xDC6B60)
        case .violet: return Color(hex: 0x7969EC)
        case .blue: return Color(hex: 0x63A2D8)
        }
    }
}

/// Order status -> tone, mirroring `StatusBadge` in apps/android.
enum OrderStatus: String {
    case paid, pending, pickup, failed, cancelled, refunded

    var label: String {
        switch self {
        case .paid: return "Paid"
        case .pending: return "Pending"
        case .pickup: return "Pickup"
        case .failed: return "Failed"
        case .cancelled: return "Cancelled"
        case .refunded: return "Refunded"
        }
    }

    var tone: BadgeTone {
        switch self {
        case .paid: return .green
        case .pending: return .yellow
        case .pickup: return .violet
        case .failed: return .red
        case .cancelled: return .neutral
        case .refunded: return .violet
        }
    }
}

/// Spacing scale from the guide: XXS 4 -> XXL 48.
enum Spacing {
    static let xxs: CGFloat = 4
    static let xs: CGFloat = 8
    static let sm: CGFloat = 12
    static let md: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
    static let xxl: CGFloat = 48
}

/// Light / Dark / System, persisted.
///
/// Defaults to LIGHT. The prototype and the Android client both render light, so
/// following the device meant the app opened dark on a dark-mode phone and no longer
/// matched the reference. System is still available for anyone who wants it.
enum AppAppearance: String, CaseIterable, Hashable, Identifiable {
    case light, dark, system

    var id: String { rawValue }

    var title: String {
        switch self {
        case .light: return "Light"
        case .dark: return "Dark"
        case .system: return "System"
        }
    }

    var symbol: String {
        switch self {
        case .light: return "sun.max"
        case .dark: return "moon"
        case .system: return "circle.lefthalf.filled"
        }
    }

    var colorScheme: ColorScheme? {
        switch self {
        case .light: return .light
        case .dark: return .dark
        case .system: return nil
        }
    }

    /// The UserDefaults key, kept in one place so RootView and the switch agree.
    static let storageKey = "app_appearance"
}
