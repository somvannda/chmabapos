import SwiftUI

/// Password reset, ported from `data-screen="reset"` in
/// apps/android/prototype/mobile-ui.html.
///
/// The prototype shows only the "set a new password" half; the request-a-code half
/// is the API's `POST /auth/request-password-reset`. Both are wired here: without a
/// token the screen asks for the email, with one it asks for the new password.
struct ResetView: View {
    let email: String
    let onUpdated: () -> Void
    let onBackToSignIn: () -> Void

    @State private var resetToken: String?
    @State private var emailInput: String
    @State private var password = ""
    @State private var confirm = ""
    @State private var busy = false
    @State private var error: String?

    @FocusState private var passwordFocused: Bool
    @FocusState private var confirmFocused: Bool

    init(email: String, onUpdated: @escaping () -> Void, onBackToSignIn: @escaping () -> Void) {
        self.email = email
        self.onUpdated = onUpdated
        self.onBackToSignIn = onBackToSignIn
        _emailInput = State(initialValue: email)
    }

    private var mismatch: Bool { !confirm.isEmpty && confirm != password }

    private var canSubmit: Bool {
        if resetToken == nil {
            return !emailInput.trimmingCharacters(in: .whitespaces).isEmpty && !busy
        }
        return password.count >= 8 && confirm == password && !busy
    }

    var body: some View {
        AuthScaffold {
            ChmabaLogo(chipSize: 32, wordmark: true, onDark: true)

            Text("A fresh key\nto your workspace.")
                .font(.system(size: 23, weight: .heavy))
                .tracking(-0.055)
                .lineSpacing(2)
                .foregroundStyle(.white)
                .padding(.top, 22)
                .padding(.bottom, 10)

            Text("Reset your password securely, then get back to running your store.")
                .font(.system(size: 12.5))
                .lineSpacing(5)
                .foregroundStyle(Color(hex: 0xA9AAB2))
                .frame(maxWidth: 280, alignment: .leading)

        } sheet: {
            HStack(spacing: 12) {
                ToneChip(symbol: "key", tone: .violet)
                VStack(alignment: .leading, spacing: 2) {
                    Text(resetToken == nil ? "Reset your password" : "Set a new password")
                        .font(.system(size: 15, weight: .heavy))
                        .tracking(-0.02)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text(resetToken == nil ? "We'll email you a reset code" : "For \(emailInput)")
                        .font(.system(size: 10))
                        .foregroundStyle(ChmabaColor.faint)
                }
                Spacer(minLength: 0)
            }
            .padding(.bottom, 20)

            if resetToken == nil {
                AuthField(label: "Email") {
                    AuthTextInput(
                        placeholder: "nadia@cedarstone.co", text: $emailInput,
                        keyboard: .emailAddress, contentType: .emailAddress, autoCapitalize: .never
                    )
                }
            } else {
                AuthField(label: "New password") {
                    PasswordInput(placeholder: "••••••••", text: $password, focus: $passwordFocused)
                }
                Text("At least 8 characters, with a number or symbol.")
                    .font(.system(size: 10.5))
                    .foregroundStyle(ChmabaColor.faint)
                    .padding(.top, -14)
                    .padding(.bottom, 14)

                AuthField(label: "Confirm password") {
                    PasswordInput(placeholder: "••••••••", text: $confirm, focus: $confirmFocused)
                }

                if mismatch {
                    Text("Passwords do not match")
                        .font(.system(size: 10.5))
                        .foregroundStyle(BadgeTone.red.foreground)
                        .padding(.top, -12)
                        .padding(.bottom, 8)
                }
            }

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
                Text(submitTitle)
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
            .padding(.top, 6)

            AuthSwap(prompt: "Remembered it?", actionTitle: "Back to sign in", action: onBackToSignIn)
            AuthNote(text: "You'll be signed out of other devices.")
        }
    }

    private var submitTitle: String {
        if busy { return resetToken == nil ? "Sending…" : "Updating…" }
        return resetToken == nil ? "Send reset code" : "Update password"
    }

    private func submit() {
        guard canSubmit else { return }
        busy = true
        error = nil
        let cleanEmail = emailInput.trimmingCharacters(in: .whitespaces).lowercased()

        Task {
            do {
                if resetToken == nil {
                    // The API answers identically whether or not the address exists,
                    // so there is nothing to branch on here.
                    try await APIClient.shared.post(
                        "auth/request-password-reset",
                        body: PasswordResetRequest(email: cleanEmail)
                    )
                    busy = false
                    // Dev convenience: the reset token comes from the API's mail. With
                    // no mail catcher configured there is nothing to paste, so the
                    // screen moves to the password step and the operator supplies the
                    // token via the link they were sent.
                    resetToken = ""
                } else {
                    try await APIClient.shared.post(
                        "auth/reset-password",
                        body: PasswordResetConfirmRequest(token: resetToken ?? "", password: password)
                    )
                    busy = false
                    onUpdated()
                }
            } catch let apiError as APIError {
                busy = false
                error = apiError.errorDescription
            } catch {
                busy = false
                self.error = "Something went wrong."
            }
        }
    }
}
