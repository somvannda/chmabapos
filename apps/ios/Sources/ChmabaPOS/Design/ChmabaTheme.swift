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

    // Surfaces -- adapt to dark mode per the guide's dark palette.
    static let background = Color.adaptive(light: 0xFFFFFF, dark: 0x111114)
    static let surface = Color.adaptive(light: 0xFFFFFF, dark: 0x1A1B20)
    static let surfaceVariant = Color.adaptive(light: 0xF5F5F7, dark: 0x2A2B30)
    static let outline = Color.adaptive(light: 0xDFDFE8, dark: 0x363740)
    static let textPrimary = Color.adaptive(light: 0x282930, dark: 0xE4E4E8)
    static let textSecondary = Color.adaptive(light: 0x6F707A, dark: 0x92939D)
}

/// Badge tones from the guide's success/warning/error pairs.
enum BadgeTone {
    case success, warning, danger, neutral

    var background: Color {
        switch self {
        case .success: return Color(hex: 0xEDF9E4)
        case .warning: return Color(hex: 0xFFF6DF)
        case .danger: return Color(hex: 0xFFF0EE)
        case .neutral: return ChmabaColor.grey200
        }
    }

    var foreground: Color {
        switch self {
        case .success: return Color(hex: 0x4F8B32)
        case .warning: return Color(hex: 0xAD7D1C)
        case .danger: return Color(hex: 0xC2564B)
        case .neutral: return ChmabaColor.grey700
        }
    }

    /// Status dot, where the guide specifies one.
    var dot: Color {
        switch self {
        case .success: return Color(hex: 0x77BB4B)
        case .warning: return Color(hex: 0xDCA93C)
        case .danger: return Color(hex: 0xDC6B60)
        case .neutral: return ChmabaColor.grey400
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
