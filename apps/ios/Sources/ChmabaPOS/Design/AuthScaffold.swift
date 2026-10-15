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
            // Tightened from the prototype's 52/44: the mark and the form were sitting
            // too far down the screen. This is a deliberate departure, so the prototype
            // remains the reference for everything else.
            .padding(.top, 24)
            .padding(.bottom, 26)
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
        .padding(.top, 20)
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

/// Sign in with Apple.
///
/// Styled to Apple's own guidance: the Apple mark plus the prescribed wording, on a
/// black field for a light background. Using Apple's button art is a requirement, not
/// a preference, so this is not restyled to match the rest of the sheet.
///
/// NOT WIRED. It cannot be, yet -- see the comment on `AuthFlowView`. The backend has
/// no `/auth/apple` endpoint and the `User` model has no `apple_sub`, so there is
/// nothing to authenticate against.
struct AppleButton: View {
    var title: String = "Sign in with Apple"
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: "apple.logo")
                    .font(.system(size: 17))
                Text(title)
                    .font(.system(size: 13, weight: .bold))
            }
            .frame(maxWidth: .infinity)
            .frame(height: 48)
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white)
        .background(Color.black, in: RoundedRectangle(cornerRadius: 12))
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

/// The 42pt rounded tone chip that heads the Verify and Reset sheets.
///
/// Colours come straight from the prototype's `--green-bg/--green-fg` and
/// `--violet-bg/--violet-fg`.
struct ToneChip: View {
    let symbol: String
    var tone: BadgeTone = .green

    var body: some View {
        RoundedRectangle(cornerRadius: 14, style: .continuous)
            .fill(tone.background)
            .frame(width: 42, height: 42)
            .overlay {
                Image(systemName: symbol)
                    .font(.system(size: 17))
                    .foregroundStyle(tone.foreground)
            }
    }
}

/// `.otp` — six single-character boxes.
///
/// 56pt tall, 20pt font 800, radius 12, and the current box takes the same purple
/// focus treatment as a text field (border `#887bf3` plus a 4pt glow).
struct OtpField: View {
    @Binding var code: String
    var length: Int = 6

    @FocusState private var focused: Bool

    /// The prototype renders a filled first box and an empty focus ring on it.
    private var digits: [String] {
        let chars = Array(code)
        return (0..<length).map { index in
            index < chars.count ? String(chars[index]) : ""
        }
    }

    private var activeIndex: Int { min(code.count, length - 1) }

    var body: some View {
        ZStack {
            // A single hidden field owns the input; the boxes only display it. This
            // gives working backspace, paste and SMS autofill for free, which six
            // separate fields do not.
            TextField("", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .focused($focused)
                .opacity(0.001)
                .onChange(of: code) { _, newValue in
                    code = String(newValue.filter(\.isNumber).prefix(length))
                }

            HStack(spacing: 8) {
                ForEach(0..<length, id: \.self) { index in
                    let isActive = focused && index == activeIndex
                    Text(digits[index])
                        .font(.system(size: 20, weight: .heavy))
                        .foregroundStyle(ChmabaColor.textPrimary)
                        .frame(maxWidth: .infinity)
                        .frame(height: 56)
                        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                        .overlay {
                            RoundedRectangle(cornerRadius: 12)
                                .strokeBorder(
                                    isActive ? ChmabaColor.focusRing : ChmabaColor.outline,
                                    lineWidth: 1
                                )
                        }
                        .overlay {
                            if isActive {
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(ChmabaColor.purple.opacity(0.10), lineWidth: 4)
                                    .padding(-4)
                            }
                        }
                }
            }
            .contentShape(Rectangle())
            .onTapGesture { focused = true }
        }
        .onAppear { focused = true }
    }
}
