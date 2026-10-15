import SwiftUI

// The auth shell, ported from apps/android/prototype/mobile-ui.html.
//
// Every auth screen is the same two-part shape:
//
//   .hero       #17181c with two radial washes (lime top-left, purple top-right),
//               padding 52/22/44, h2 26px 800 -0.055em, p 12.5px #a9aab2 max 280
//   .sheetcard  white, radius 24 24 0 0, pulled up 18pt, padding 26/22/28
//
// The values here are the prototype's own, not approximations of Android's Kotlin --
// the prototype is the design source and SCREENS.md is explicit that colours, radii
// and wording must not drift.

/// The dark hero at the top of every auth screen.
struct AuthHero<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        ZStack {
            ChmabaColor.inkStrong

            // radial-gradient(circle at 12% 18%, rgba(185,238,111,.16), transparent 26%)
            RadialGradient(
                colors: [Color(hex: 0xB9EE6F).opacity(0.16), .clear],
                center: UnitPoint(x: 0.12, y: 0.18),
                startRadius: 0,
                endRadius: 60
            )
            // radial-gradient(circle at 84% 8%, rgba(105,87,245,.18), transparent 28%)
            RadialGradient(
                colors: [ChmabaColor.purple.opacity(0.18), .clear],
                center: UnitPoint(x: 0.84, y: 0.08),
                startRadius: 0,
                endRadius: 120
            )

            VStack(alignment: .leading, spacing: 0) {
                content()
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 22)
            .padding(.top, 52)
            .padding(.bottom, 44)
        }
        // NOTE: no corner radius. The prototype's `.hero` is square-bottomed --
        // only `.sheetcard` is rounded (24pt on its top edge), and it overlaps the
        // hero by 18pt. Rounding the hero here put a curve where the design has a
        // straight edge, and the sheet no longer sat flush against it.
    }
}

/// The white sheet that carries the form, overlapping the hero by 18pt.
struct AuthSheet<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 22)
        .padding(.top, 26)
        .padding(.bottom, 28)
        .background(ChmabaColor.surface)
        .clipShape(
            UnevenRoundedRectangle(topLeadingRadius: 24, topTrailingRadius: 24, style: .continuous)
        )
        // The 18pt overlap with the hero is applied by AuthScaffold as negative
        // padding on the hero, NOT as an offset here. `offset` moves the view
        // visually without changing its layout box, which left an 18pt band at the
        // bottom of the screen showing the page background instead of the sheet.
    }
}

/// Full auth screen: hero above, sheet below.
///
/// Two layout rules from the prototype that are easy to get wrong and both show up
/// as the sheet appearing "cut off" at the bottom of the screen:
///
///   - `.sheetcard` is `flex: 1`, so the sheet takes ALL remaining height and the
///     white reaches the bottom edge. Sizing it to its content leaves the page
///     background visible underneath the form.
///   - the sheet overlaps the hero by 18pt (`margin-top: -18px`). That is applied
///     as negative padding on the hero so the layout box shrinks with it; an
///     `offset` would move the sheet visually but leave an uncovered band.
struct AuthScaffold<Hero: View, Sheet: View>: View {
    @ViewBuilder var hero: () -> Hero
    @ViewBuilder var sheet: () -> Sheet

    /// Prototype's `margin-top: -18px` on `.sheetcard`.
    private let overlap: CGFloat = 18

    var body: some View {
        GeometryReader { proxy in
            ScrollView {
                VStack(spacing: 0) {
                    AuthHero { hero() }
                        .padding(.bottom, -overlap)

                    AuthSheet { sheet() }
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                }
                .frame(minHeight: proxy.size.height, alignment: .top)
            }
            .background(ChmabaColor.background)
            .scrollDismissesKeyboard(.interactively)
        }
        // The sheet runs to the physical bottom edge; only the top is inset.
        .ignoresSafeArea(edges: .bottom)
    }
}

// MARK: - Shared auth pieces

/// `.or` — a hairline rule either side of a small centred label.
struct OrDivider: View {
    var text: String = "or continue with"

    var body: some View {
        HStack(spacing: 11) {
            Rectangle().fill(ChmabaColor.border).frame(height: 1)
            Text(text)
                .font(.system(size: 10, weight: .bold))
                .tracking(0.02)
                .foregroundStyle(ChmabaColor.faint)
                .fixedSize()
            Rectangle().fill(ChmabaColor.border).frame(height: 1)
        }
        .padding(.vertical, 18)
    }
}

/// `.gbtn` — 48pt outlined button with the Google mark at 17pt.
struct GoogleButton: View {
    var title: String = "Continue with Google"
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                brandImage("google-g")
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .frame(width: 17, height: 17)
                Text(title)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color(hex: 0x282930))
            }
            .frame(maxWidth: .infinity)
            .frame(height: 48)
        }
        .buttonStyle(.plain)
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
        .overlay {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(ChmabaColor.borderStrong, lineWidth: 1)
        }
    }
}

/// `.authswap` — "New to Chmaba? **Create an account**".
struct AuthSwap: View {
    let prompt: String
    let actionTitle: String
    let action: () -> Void

    var body: some View {
        HStack(spacing: 5) {
            Text(prompt)
                .font(.system(size: 12.5))
                .foregroundStyle(ChmabaColor.muted)
            Button(action: action) {
                Text(actionTitle)
                    .font(.system(size: 12.5, weight: .bold))
                    .foregroundStyle(ChmabaColor.purple)
            }
            .buttonStyle(.plain)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 20)
    }
}

/// `.authnote` — the small footer line.
struct AuthNote: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 10.5))
            .foregroundStyle(ChmabaColor.faint)
            .multilineTextAlignment(.center)
            .lineSpacing(4)
            .frame(maxWidth: .infinity)
            .padding(.top, 18)
    }
}

/// `.field` — label above a 47pt input, focused with a purple border and a 4pt glow.
struct AuthField<Content: View>: View {
    let label: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label)
                .font(.system(size: 11, weight: .bold))
                .tracking(0.01)
                .foregroundStyle(ChmabaColor.textSecondary)
            content()
        }
        .padding(.bottom, 20)
    }
}

/// `.pwrap` + `.eye` — a password input with a 35pt reveal button inset at 6pt.
struct PasswordInput: View {
    let placeholder: String
    @Binding var text: String
    @State private var revealed = false
    var focus: FocusState<Bool>.Binding

    var body: some View {
        HStack(spacing: 0) {
            Group {
                if revealed {
                    TextField(placeholder, text: $text)
                } else {
                    SecureField(placeholder, text: $text)
                }
            }
            .focused(focus)
            .textContentType(.password)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()

            Button {
                revealed.toggle()
            } label: {
                Image(systemName: revealed ? "eye.slash" : "eye")
                    .font(.system(size: 15))
                    .foregroundStyle(ChmabaColor.ghost)
                    .frame(width: 35, height: 35)
            }
            .buttonStyle(.plain)
        }
        .padding(.leading, 13)
        .padding(.trailing, 6)
        .frame(height: 47)
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 13))
        .overlay {
            RoundedRectangle(cornerRadius: 13)
                .strokeBorder(ChmabaColor.outline, lineWidth: 1)
        }
    }
}

/// A plain 47pt input styled like `AuthField`'s content.
struct AuthTextInput: View {
    let placeholder: String
    @Binding var text: String
    var keyboard: UIKeyboardType = .default
    var contentType: UITextContentType?
    var autoCapitalize: TextInputAutocapitalization = .sentences

    var body: some View {
        TextField(placeholder, text: $text)
            .keyboardType(keyboard)
            .textContentType(contentType)
            .textInputAutocapitalization(autoCapitalize)
            .autocorrectionDisabled(keyboard == .emailAddress)
            .padding(.horizontal, 13)
            .frame(height: 47)
            .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 13))
            .overlay {
                RoundedRectangle(cornerRadius: 13)
                    .strokeBorder(ChmabaColor.outline, lineWidth: 1)
            }
    }
}
