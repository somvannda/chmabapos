import SwiftUI

/// Email verification, ported from `data-screen="verify"` in
/// apps/android/prototype/mobile-ui.html.
///
/// The prototype's "From Gmail" strip is a presentation of the OS one-time-code
/// suggestion, not an app control. Here it is made genuinely useful in dev: the API
/// returns `dev_verification_token` from `/auth/register` when mail is not
/// configured, so the strip shows that code's prefix and fills the field when tapped.
/// With real SMTP configured the token is absent and the strip is simply hidden.
struct VerifyView: View {
    let email: String
    let devToken: String?
    let onVerified: () -> Void
    let onUseDifferentEmail: () -> Void

    @State private var code = ""
    @State private var busy = false
    @State private var error: String?

    private let length = 6

    var body: some View {
        AuthScaffold {
            ChmabaLogo(chipSize: 32, wordmark: true, onDark: true)

            Text("Confirm your email.")
                .font(.system(size: 23, weight: .heavy))
                .tracking(-0.055)
                .foregroundStyle(.white)
                .padding(.top, 22)
                .padding(.bottom, 10)

            Text("One quick step to secure your workspace.")
                .font(.system(size: 12.5))
                .lineSpacing(5)
                .foregroundStyle(Color(hex: 0xA9AAB2))
                .frame(maxWidth: 280, alignment: .leading)

        } sheet: {
            HStack(spacing: 12) {
                ToneChip(symbol: "envelope", tone: .green)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Check your inbox")
                        .font(.system(size: 15, weight: .heavy))
                        .tracking(-0.02)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("We sent a 6-digit code to \(email)")
                        .font(.system(size: 10))
                        .foregroundStyle(ChmabaColor.faint)
                }
                Spacer(minLength: 0)
            }
            .padding(.bottom, 18)

            OtpField(code: $code, length: length)
                .padding(.bottom, 10)

            Text("Didn't get it? Resend in 0:24")
                .font(.system(size: 10))
                .foregroundStyle(ChmabaColor.faint)
                .frame(maxWidth: .infinity)
                .padding(.bottom, 16)

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
                Text(busy ? "Confirming…" : "Confirm email & continue")
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
            .padding(.top, 16)

            if let devToken, devToken.count >= 3 {
                devSuggestion(devToken)
            }

            Text("Tap the suggestion above the keyboard. Chmaba never reads your inbox.")
                .font(.system(size: 10))
                .foregroundStyle(ChmabaColor.faint)
                .multilineTextAlignment(.center)
                .lineSpacing(3)
                .frame(maxWidth: .infinity)
                .padding(.top, 8)

            Button("Use a different email", action: onUseDifferentEmail)
                .buttonStyle(.plain)
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(ChmabaColor.muted)
                .frame(maxWidth: .infinity)
                .padding(.top, 10)
        }
    }

    private var canSubmit: Bool { code.count == length && !busy }

    /// The prototype's `.otpsuggest` strip.
    private func devSuggestion(_ token: String) -> some View {
        Button {
            code = token
        } label: {
            HStack(spacing: 11) {
                RoundedRectangle(cornerRadius: 9)
                    .fill(ChmabaColor.surface)
                    .frame(width: 28, height: 28)
                    .overlay {
                        Image(systemName: "envelope")
                            .font(.system(size: 13))
                            .foregroundStyle(Color(hex: 0xEA4335))
                    }
                    .shadow(color: Color(hex: 0x14151C).opacity(0.1), radius: 1.5, y: 1)

                VStack(alignment: .leading, spacing: 2) {
                    Text("\(token.prefix(3))•••")
                        .font(.system(size: 15, weight: .heavy))
                        .tracking(3.6)                       // .24em
                        .foregroundStyle(ChmabaColor.purple)
                    Text("From Gmail")                        // prototype's label
                        .font(.system(size: 10))
                        .foregroundStyle(ChmabaColor.muted)
                }

                Spacer()

                Image(systemName: "checkmark")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(ChmabaColor.purple)
            }
            .padding(.horizontal, 13)
            .padding(.vertical, 11)
            .background(ChmabaColor.backgroundAlt, in: RoundedRectangle(cornerRadius: 14))
            .overlay {
                RoundedRectangle(cornerRadius: 14).strokeBorder(ChmabaColor.border, lineWidth: 1)
            }
        }
        .buttonStyle(.plain)
        .padding(.top, 14)
    }

    private func submit() {
        guard canSubmit else { return }
        busy = true
        error = nil
        Task {
            do {
                let _: UserRead = try await APIClient.shared.post(
                    "auth/verify-email", body: VerifyEmailRequest(token: code), as: UserRead.self
                )
                busy = false
                onVerified()
            } catch let apiError as APIError {
                busy = false
                error = apiError.errorDescription
            } catch {
                busy = false
                self.error = "Could not confirm the code."
            }
        }
    }
}
