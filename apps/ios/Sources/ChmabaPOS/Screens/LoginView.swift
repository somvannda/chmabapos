import SwiftUI

/// Login, ported from the prototype (`data-screen="login"`) in
/// apps/android/prototype/mobile-ui.html.
///
/// Structure is the standard auth two-parter: a dark hero carrying the brand and the
/// promise, then a white sheet with the form. The strings, sizes and spacing are the
/// prototype's own -- SCREENS.md is explicit that wording and copy must not change.
///
/// Google sign-in is present because the prototype shows it, but it is not wired:
/// it needs the OAuth CSRF cookie and a redirect URI registered against `localhost`,
/// which a device on the LAN cannot satisfy. See docs/ios-platform-options.md
/// Appendix B.
struct LoginView: View {
    @EnvironmentObject private var session: Session

    /// Defaults keep the view usable standalone; AuthFlow supplies the real ones.
    var onSignUp: () -> Void = {}
    var onForgotPassword: () -> Void = {}

    @State private var email = ""
    @State private var password = ""
    @State private var rememberMe = true          // prototype defaults this checked
    @FocusState private var passwordFocused: Bool

    private var canSubmit: Bool {
        !email.trimmingCharacters(in: .whitespaces).isEmpty
            && !password.isEmpty
            && !session.isSigningIn
    }

    var body: some View {
        AuthScaffold {
            // MARK: hero
            ChmabaLogo(chipSize: 32, wordmark: true, onDark: true)

            Text("A clearer way\nto run your day.")
                .font(.system(size: 26, weight: .heavy))
                .tracking(-0.055)
                .lineSpacing(2)
                .foregroundStyle(.white)
                .padding(.top, 22)
                .padding(.bottom, 10)

            Text("One home for every sale, every item, and every small win.")
                .font(.system(size: 12.5))
                .lineSpacing(5)
                .foregroundStyle(Color(hex: 0xA9AAB2))
                .frame(maxWidth: 280, alignment: .leading)

        } sheet: {
            // MARK: sheet
            Text("Welcome back")
                .font(.system(size: 22, weight: .heavy))
                .tracking(-0.05)
                .foregroundStyle(ChmabaColor.textPrimary)

            Text("Sign in to your workspace.")
                .font(.system(size: 11))
                .foregroundStyle(ChmabaColor.muted)
                .padding(.top, 2)
                .padding(.bottom, 20)

            AuthField(label: "Email") {
                AuthTextInput(
                    placeholder: "you@store.com",
                    text: $email,
                    keyboard: .emailAddress,
                    contentType: .username,
                    autoCapitalize: .never
                )
            }

            AuthField(label: "Password") {
                PasswordInput(
                    placeholder: "••••••••",
                    text: $password,
                    focus: $passwordFocused
                )
            }

            HStack {
                Button {
                    rememberMe.toggle()
                } label: {
                    HStack(spacing: 7) {
                        Checkbox(checked: rememberMe)
                        Text("Remember me")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(ChmabaColor.textSecondary)
                    }
                }
                .buttonStyle(.plain)

                Spacer()

                Button("Forgot password?", action: onForgotPassword)
                    .buttonStyle(.plain)
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
            .padding(.bottom, 18)

            if let error = session.signInError {
                Text(error)
                    .font(.system(size: 11.5))
                    .foregroundStyle(Color(hex: 0xC2564B))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color(hex: 0xFFF5F3), in: RoundedRectangle(cornerRadius: 12))
                    .padding(.bottom, 14)
            }

            Button(action: submit) {
                Text(session.isSigningIn ? "Signing in…" : "Sign in")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
            }
            .buttonStyle(.plain)
            .background(
                canSubmit ? ChmabaColor.purple : ChmabaColor.purple.opacity(0.45),
                in: RoundedRectangle(cornerRadius: 12)
            )
            .disabled(!canSubmit)

            OrDivider()

            GoogleButton { /* not wired: see the type comment */ }

            AuthSwap(prompt: "New to Chmaba?", actionTitle: "Create an account", action: onSignUp)

            AuthNote(text: "Protected by Cloudflare Turnstile")
        }
    }

    private func submit() {
        guard canSubmit else { return }
        passwordFocused = false
        Task {
            await session.signIn(email: email, password: password, remember: rememberMe)
        }
    }
}

/// The prototype's `<input type="checkbox">`, 22pt with a purple checked fill.
struct Checkbox: View {
    let checked: Bool

    var body: some View {
        RoundedRectangle(cornerRadius: 6)
            .fill(checked ? ChmabaColor.purple : ChmabaColor.surface)
            .frame(width: 22, height: 22)
            .overlay {
                RoundedRectangle(cornerRadius: 6)
                    .strokeBorder(checked ? ChmabaColor.purple : ChmabaColor.ghost, lineWidth: 1.5)
            }
            .overlay {
                if checked {
                    Image(systemName: "checkmark")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(.white)
                }
            }
    }
}
