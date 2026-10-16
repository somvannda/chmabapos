import SwiftUI

/// Signup, ported from `data-screen="signup"` in
/// apps/android/prototype/mobile-ui.html.
struct SignupView: View {
    let onSignIn: () -> Void
    /// Hands the credentials up so the flow can sign in once the email is confirmed,
    /// plus the dev verification token when the API returns one.
    let onRegistered: (_ email: String, _ password: String, _ devToken: String?) -> Void
    /// Same treatment as LoginView: the providers are shown but not wired, and saying
    /// so beats a button that does nothing.
    var onProviderUnavailable: (String) -> Void = { _ in }

    @State private var fullName = ""
    @State private var email = ""
    @State private var phone = ""
    @State private var password = ""
    @State private var confirm = ""
    @State private var agreed = false
    @State private var busy = false
    @State private var error: String?

    @FocusState private var passwordFocused: Bool
    @FocusState private var confirmFocused: Bool

    private var mismatch: Bool { !confirm.isEmpty && confirm != password }

    private var canSubmit: Bool {
        !fullName.trimmingCharacters(in: .whitespaces).isEmpty
            && !email.trimmingCharacters(in: .whitespaces).isEmpty
            && password.count >= 8
            && confirm == password
            && agreed
            && !busy
    }

    var body: some View {
        AuthScaffold {
            ChmabaLogo(chipSize: 32, wordmark: true, onDark: true)

            Text("Create your workspace.")
                .font(.system(size: 23, weight: .heavy))
                .tracking(-0.055)
                .foregroundStyle(.white)
                .padding(.top, 22)
                .padding(.bottom, 10)

            Text("Free to start — no payment details needed.")
                .font(.system(size: 12.5))
                .lineSpacing(5)
                .foregroundStyle(Color(hex: 0xA9AAB2))
                .frame(maxWidth: 280, alignment: .leading)

        } sheet: {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Tell us about you")
                        .font(.system(size: 16, weight: .heavy))
                        .tracking(-0.02)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("You can invite your team later")
                        .font(.system(size: 10))
                        .foregroundStyle(ChmabaColor.faint)
                }
                Spacer()
                Button("Sign in", action: onSignIn)
                    .buttonStyle(.plain)
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(ChmabaColor.muted)
            }
            .padding(.bottom, 18)

            AuthField(label: "Full name") {
                AuthTextInput(placeholder: "e.g. Nadia Sok", text: $fullName, contentType: .name)
            }
            AuthField(label: "Email") {
                AuthTextInput(
                    placeholder: "nadia@cedarstone.co", text: $email,
                    keyboard: .emailAddress, contentType: .emailAddress, autoCapitalize: .never
                )
            }
            AuthField(label: "Phone") {
                AuthTextInput(placeholder: "+855 …", text: $phone, keyboard: .phonePad, contentType: .telephoneNumber)
            }

            HStack(alignment: .top, spacing: 12) {
                AuthField(label: "Password") {
                    PasswordInput(placeholder: "••••••••", text: $password, focus: $passwordFocused)
                }
                AuthField(label: "Confirm") {
                    PasswordInput(placeholder: "••••••••", text: $confirm, focus: $confirmFocused)
                }
            }

            if mismatch {
                Text("Passwords do not match")
                    .font(.system(size: 10.5))
                    .foregroundStyle(BadgeTone.red.foreground)
                    .padding(.top, -12)
                    .padding(.bottom, 8)
            }

            Button {
                agreed.toggle()
            } label: {
                HStack(spacing: 8) {
                    Checkbox(checked: agreed)
                    Text("I agree to the Terms and Privacy Policy")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.textSecondary)
                }
            }
            .buttonStyle(.plain)
            .padding(.top, 4)
            .padding(.bottom, 18)

            if let error {
                Text(error)
                    .font(.system(size: 11.5))
                    .foregroundStyle(Color(hex: 0xC2564B))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color(hex: 0xFFF5F3), in: RoundedRectangle(cornerRadius: 12))
                    .padding(.bottom, 14)
            }

            Button(action: submit) {
                Text(busy ? "Creating…" : "Create account")
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

            // Apple first, then Google -- matching LoginView.
            AppleButton(title: "Sign up with Apple") {
                onProviderUnavailable("Sign in with Apple")
            }
            .padding(.bottom, 10)

            GoogleButton(title: "Sign up with Google") {
                onProviderUnavailable("Google sign-in")
            }

            AuthSwap(prompt: "Already have an account?", actionTitle: "Sign in", action: onSignIn)
        }
    }

    private func submit() {
        guard canSubmit else { return }
        busy = true
        error = nil
        Task {
            do {
                let body = RegisterRequest(
                    email: email.trimmingCharacters(in: .whitespaces).lowercased(),
                    fullName: fullName.trimmingCharacters(in: .whitespaces),
                    password: password
                )
                // /auth/register returns dev_verification_token when mail is not
                // configured, which is why the next screen can be completed in dev
                // without a mail catcher.
                let registered: RegisterResponse = try await APIClient.shared.post(
                    "auth/register", body: body, as: RegisterResponse.self
                )
                busy = false
                onRegistered(
                    email.trimmingCharacters(in: .whitespaces).lowercased(),
                    password,
                    registered.devVerificationToken
                )
            } catch let apiError as APIError {
                busy = false
                error = apiError.errorDescription
            } catch {
                busy = false
                self.error = "Could not create the account."
            }
        }
    }
}
