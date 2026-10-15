import SwiftUI

/// Sign-in screen.
///
/// Scope note: email + password only. Google sign-in is deliberately omitted — it
/// depends on the OAuth CSRF cookie and a redirect URI registered against
/// `localhost`, neither of which works from a device on the LAN. See
/// docs/ios-platform-options.md Appendix B.
///
/// Built from the shared components in Design/ChmabaComponents.swift so this screen
/// matches the Android client's field/button treatment rather than re-styling it.
struct LoginView: View {
    @EnvironmentObject private var session: Session

    @State private var email = ""
    @State private var password = ""
    @State private var rememberMe = false
    @State private var showPassword = false
    @FocusState private var focus: Field?

    private enum Field { case email, password }

    private var canSubmit: Bool {
        !email.trimmingCharacters(in: .whitespaces).isEmpty
            && !password.isEmpty
            && !session.isSigningIn
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Spacing.lg) {
                header
                if let error = session.signInError {
                    errorBanner(error)
                }
                form
                submitButton
                footer
            }
            .padding(Spacing.lg)
            .frame(maxWidth: 480)
            .frame(maxWidth: .infinity)
        }
        .background(ChmabaColor.background)
        .scrollDismissesKeyboard(.interactively)
    }

    // MARK: Sections

    private var header: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            ChmabaLogo(chipSize: 32, wordmark: true)
            Text("Welcome back")
                .font(.system(size: 32, weight: .heavy))
                .foregroundStyle(ChmabaColor.textPrimary)
                .padding(.top, Spacing.sm)
            Text("Sign in to open your till.")
                .font(.system(size: 14))
                .foregroundStyle(ChmabaColor.textSecondary)
        }
    }

    private func errorBanner(_ message: String) -> some View {
        HStack(alignment: .top, spacing: Spacing.xs) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(BadgeTone.red.foreground)
            Text(message)
                .font(.system(size: 13))
                .foregroundStyle(BadgeTone.red.foreground)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Spacing.sm)
        .background(BadgeTone.red.background, in: RoundedRectangle(cornerRadius: 12))
    }

    private var form: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            ChmabaField(label: "Email") {
                TextField("you@example.com", text: $email)
                    .textContentType(.username)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .focused($focus, equals: .email)
                    .submitLabel(.next)
                    .onSubmit { focus = .password }
            }

            ChmabaField(label: "Password") {
                HStack(spacing: 8) {
                    Group {
                        if showPassword {
                            TextField("Your password", text: $password)
                        } else {
                            SecureField("Your password", text: $password)
                        }
                    }
                    .textContentType(.password)
                    .focused($focus, equals: .password)
                    .submitLabel(.go)
                    .onSubmit { submit() }

                    // Matches Android's PasswordField show/hide affordance.
                    Button {
                        showPassword.toggle()
                    } label: {
                        Image(systemName: showPassword ? "eye.slash" : "eye")
                            .foregroundStyle(ChmabaColor.grey400)
                    }
                    .buttonStyle(.plain)
                }
            }

            Toggle(isOn: $rememberMe) {
                Text("Keep me signed in")
                    .font(.system(size: 13))
                    .foregroundStyle(ChmabaColor.textPrimary)
            }
            .tint(ChmabaColor.purple)
        }
    }

    private var submitButton: some View {
        ChmabaButton(
            text: "Sign in",
            variant: .primary,
            size: .large,
            enabled: canSubmit,
            fullWidth: true,
            loading: session.isSigningIn,
            action: submit
        )
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: Spacing.xxs) {
            Text(APIConfig.baseURL.absoluteString)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(ChmabaColor.textSecondary)
            Text("Google sign-in is not available on iOS yet.")
                .font(.system(size: 10))
                .foregroundStyle(ChmabaColor.textSecondary)
        }
        .padding(.top, Spacing.sm)
    }

    private func submit() {
        guard canSubmit else { return }
        focus = nil
        Task {
            await session.signIn(email: email, password: password, remember: rememberMe)
        }
    }
}
