import SwiftUI

/// Login, ported from the prototype (`data-screen="login"`) in
/// apps/android/prototype/mobile-ui.html.
///
/// Structure is the standard auth two-parter: a dark hero carrying the brand and the
/// promise, then a white sheet with the form. The strings, sizes and spacing are the
/// prototype's own -- SCREENS.md is explicit that wording and copy must not change.
struct LoginView: View {
    @EnvironmentObject private var session: Session

    /// Defaults keep the view usable standalone; AuthFlow supplies the real ones.
    var onSignUp: () -> Void = {}
    var onForgotPassword: () -> Void = {}
    /// Called when a social provider is tapped. It shows what is missing rather than
    /// doing nothing, which would look like a broken button.
    var onProviderUnavailable: (String) -> Void = { _ in }

    @State private var email = ""
    @State private var password = ""
    @State private var rememberMe = true          // prototype defaults this checked
    @State private var serverSheet = false
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
                .padding(.top, 18)
                .padding(.bottom, 8)

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
                .padding(.bottom, 16)

            if let failure = session.signInError {
                errorCard(failure)
                    .padding(.bottom, 16)
            }

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
            .padding(.bottom, 16)

            ChmabaButton(
                text: session.isSigningIn ? "Signing in…" : "Sign in",
                variant: .primary,
                size: .large,
                enabled: canSubmit,
                fullWidth: true,
                loading: session.isSigningIn,
                action: submit
            )

            OrDivider()

            // Apple first, then Google -- as requested.
            //
            // Both are present but NOT wired, and tapping either says so rather than
            // failing silently. The backend has no /auth/apple endpoint at all and no
            // apple_sub column, and /auth/google verifies the ID token against a single
            // web client id (config.py:36) that a native iOS sign-in would not match.
            // See AuthFlowView for the full note.
            AppleButton {
                onProviderUnavailable("Sign in with Apple")
            }
            .padding(.bottom, 10)

            GoogleButton(title: "Continue with Google") {
                onProviderUnavailable("Google sign-in")
            }

            AuthSwap(prompt: "New to Chmaba?", actionTitle: "Create an account", action: onSignUp)

            serverRow

            AuthNote(text: "Protected by Cloudflare Turnstile")
        }
        .sheet(isPresented: $serverSheet) {
            ServerSettingsSheet()
        }
    }

    // MARK: Error

    /// A structured failure: what happened, why, and what to do next. The old version
    /// was one sentence, which left an operator with no idea which end to check.
    private func errorCard(_ failure: Session.SignInFailure) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                Text(failure.title)
                    .font(.system(size: 13, weight: .bold))
            }
            .foregroundStyle(BadgeTone.red.foreground)

            Text(failure.message)
                .font(.system(size: 12.5))
                .foregroundStyle(ChmabaColor.textPrimary)
                .fixedSize(horizontal: false, vertical: true)

            if let suggestion = failure.suggestion {
                Text(suggestion)
                    .font(.system(size: 11.5))
                    .lineSpacing(2)
                    .foregroundStyle(ChmabaColor.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Button {
                serverSheet = true
            } label: {
                Text("Connection settings")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(ChmabaColor.purple)
            }
            .buttonStyle(.plain)
            .padding(.top, 2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(BadgeTone.red.background, in: RoundedRectangle(cornerRadius: 12))
        .overlay(alignment: .leading) {
            // A left rule reads as a notice rather than an alarm, which suits a
            // recoverable connection problem.
            Rectangle()
                .fill(BadgeTone.red.foreground)
                .frame(width: 3)
                .clipShape(RoundedRectangle(cornerRadius: 2))
                .padding(.vertical, 10)
        }
    }

    // MARK: Server row

    private var serverRow: some View {
        Button {
            serverSheet = true
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "network")
                    .font(.system(size: 12))
                    .foregroundStyle(ChmabaColor.ghost)
                Text("Server")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
                Spacer()
                Text(APIConfig.hostDescription)
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                    .foregroundStyle(ChmabaColor.textSecondary)
                    .lineLimit(1)
                Image(systemName: "chevron.right")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.ghost)
            }
            .padding(.horizontal, 12)
            .frame(height: 40)
            .background(ChmabaColor.backgroundAlt, in: RoundedRectangle(cornerRadius: 10))
            .overlay {
                RoundedRectangle(cornerRadius: 10).strokeBorder(ChmabaColor.border, lineWidth: 1)
            }
        }
        .buttonStyle(ChmabaPressStyle())
        .padding(.top, 16)
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

/// Lets an operator point the app at a different API address without a rebuild.
///
/// This exists because the dev server's address depends on which network the device is
/// on, and the machine running it has two candidate addresses on different subnets.
/// Pinning one in code meant a rebuild every time the answer changed.
struct ServerSettingsSheet: View {
    @Environment(\.dismiss) private var dismiss

    @State private var address = APIConfig.baseURLString
    @State private var testing = false
    @State private var result: ConnectionTest?

    /// `Result` requires its failure type to conform to `Error`, which `String` does
    /// not -- so a small enum rather than `Result<String, String>`.
    enum ConnectionTest: Equatable {
        case connected(String)
        case unreachable(String)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Point this app at your API.")
                        .font(.system(size: 13))
                        .foregroundStyle(ChmabaColor.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)

                    AuthField(label: "API base URL") {
                        TextField(APIConfig.fallbackString, text: $address)
                            .keyboardType(.URL)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .font(.system(size: 13, design: .monospaced))
                            .padding(.horizontal, 13)
                            .frame(height: 47)
                            .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 13))
                            .overlay {
                                RoundedRectangle(cornerRadius: 13)
                                    .strokeBorder(ChmabaColor.outline, lineWidth: 1)
                            }
                    }
                    .padding(.top, 16)

                    Text("Include the /api/v1/ suffix. Use the address of the machine running the API, not localhost — on a device, localhost is the device itself.")
                        .font(.system(size: 10.5))
                        .lineSpacing(2)
                        .foregroundStyle(ChmabaColor.faint)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, -10)

                    HStack(spacing: 10) {
                        ChmabaButton(text: "Save", variant: .primary, size: .medium, fullWidth: true) {
                            APIConfig.baseURLString = address.trimmingCharacters(in: .whitespacesAndNewlines)
                            test()
                        }
                        ChmabaButton(text: "Test", variant: .outline, size: .medium, fullWidth: true) {
                            test()
                        }
                    }
                    .padding(.top, 18)

                    if let result {
                        switch result {
                        case let .connected(detail):
                            notice(tone: .green, title: "Connected", detail: detail)
                        case let .unreachable(message):
                            notice(tone: .red, title: "No answer", detail: message)
                        }
                    }

                    ChmabaButton(text: "Reset to default", variant: .ghost, size: .small) {
                        APIConfig.reset()
                        address = APIConfig.baseURLString
                        result = nil
                    }
                    .padding(.top, 18)
                }
                .padding(20)
            }
            .background(ChmabaColor.surface)
            .navigationTitle("Connection")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func notice(tone: BadgeTone, title: String, detail: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 12.5, weight: .bold))
                .foregroundStyle(tone.foreground)
            Text(detail)
                .font(.system(size: 11.5))
                .foregroundStyle(ChmabaColor.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(tone.background, in: RoundedRectangle(cornerRadius: 12))
        .padding(.top, 14)
    }

    /// Hits the API's health endpoint on the address in the field, independently of
    /// whatever is saved, so a typo can be caught before signing in.
    private func test() {
        let trimmed = address.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed)?.appending(path: "health") else {
            result = .unreachable("That is not a valid URL.")
            return
        }
        testing = true
        result = nil
        Task {
            var request = URLRequest(url: url)
            request.timeoutInterval = 8
            do {
                let (data, response) = try await URLSession.shared.data(for: request)
                let status = (response as? HTTPURLResponse)?.statusCode ?? 0
                let body = String(data: data, encoding: .utf8) ?? ""
                testing = false
                if (200..<300).contains(status) {
                    result = .connected("HTTP \(status) — \(body)")
                } else {
                    result = .unreachable("HTTP \(status) — \(body)")
                }
            } catch {
                testing = false
                result = .unreachable("\(error.localizedDescription)\n\nIf this times out, the device is probably on a different network from the API, or a firewall is blocking the port.")
            }
        }
    }
}
