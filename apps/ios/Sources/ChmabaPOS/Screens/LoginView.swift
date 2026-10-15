import SwiftUI

/// Sign-in screen.
///
/// Scope note: email + password only for now. Google sign-in is deliberately
/// omitted, because it depends on the OAuth CSRF cookie and a redirect URI
/// registered against `localhost` -- neither of which works from a device on the
/// LAN. See docs/ios-platform-options.md Appendix B.
struct LoginView: View {
    @EnvironmentObject private var session: Session

    @State private var email = ""
    @State private var password = ""
    @State private var rememberMe = false
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
            ChmabaLogo(size: 48)
            Text("Welcome back")
                .font(.largeTitle.weight(.bold))
                .foregroundStyle(ChmabaColor.textPrimary)
                .padding(.top, Spacing.sm)
            Text("Sign in to open your till.")
                .font(.subheadline)
                .foregroundStyle(ChmabaColor.textSecondary)
        }
    }

    private func errorBanner(_ message: String) -> some View {
        HStack(alignment: .top, spacing: Spacing.xs) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(BadgeTone.danger.foreground)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(BadgeTone.danger.foreground)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Spacing.sm)
        .background(BadgeTone.danger.background, in: RoundedRectangle(cornerRadius: 12))
    }

    private var form: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            ChmabaField(label: "Email", text: $email) {
                TextField("you@example.com", text: $email)
                    .textContentType(.username)
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .focused($focus, equals: .email)
                    .submitLabel(.next)
                    .onSubmit { focus = .password }
            }

            ChmabaField(label: "Password", text: $password) {
                SecureField("Your password", text: $password)
                    .textContentType(.password)
                    .focused($focus, equals: .password)
                    .submitLabel(.go)
                    .onSubmit { submit() }
            }

            Toggle(isOn: $rememberMe) {
                Text("Keep me signed in")
                    .font(.subheadline)
                    .foregroundStyle(ChmabaColor.textPrimary)
            }
            .tint(ChmabaColor.purple)
        }
    }

    private var submitButton: some View {
        Button(action: submit) {
            HStack(spacing: Spacing.xs) {
                if session.isSigningIn {
                    ProgressView().tint(.white)
                }
                Text(session.isSigningIn ? "Signing in…" : "Sign in")
                    .font(.headline)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 48)
        }
        .background(
            canSubmit ? ChmabaColor.purple : ChmabaColor.grey400,
            in: RoundedRectangle(cornerRadius: 12)
        )
        .foregroundStyle(.white)
        .disabled(!canSubmit)
        .animation(.easeOut(duration: 0.15), value: canSubmit)
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: Spacing.xxs) {
            Text(APIConfig.baseURL.absoluteString)
                .font(.caption2.monospaced())
                .foregroundStyle(ChmabaColor.textSecondary)
            Text("Google sign-in is not available on iOS yet.")
                .font(.caption2)
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

/// Labelled text field matching the guide's 44pt / 12pt-radius spec.
struct ChmabaField<Content: View>: View {
    let label: String
    @Binding var text: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.xxs) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(ChmabaColor.textSecondary)
            content()
                .textFieldStyle(.plain)
                .padding(.horizontal, Spacing.sm)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.outline, lineWidth: 1)
                )
        }
    }
}
