import SwiftUI

/// The signed-out flow, mirroring `AppRoot.kt`'s `AppScreen` state machine.
///
/// Android drives this with a `sealed interface` plus a `Crossfade`; the same shape
/// works here, and `BackHandler`'s unwind is replaced by the explicit transitions
/// below.
enum AuthScreen: Equatable {
    case login
    case signup
    case verify
    case reset
}

struct AuthFlowView: View {
    @EnvironmentObject private var session: Session

    @State private var screen: AuthScreen = .login
    @State private var activeEmail = ""
    /// Held so the flow can sign in straight after the email is confirmed -- the
    /// API refuses a login for an unverified account, so verification has to happen
    /// between registering and entering the app.
    @State private var pendingPassword = ""
    @State private var devToken: String?

    var body: some View {
        ZStack {
            switch screen {
            case .login:
                LoginView(
                    onSignUp: { go(.signup) },
                    onForgotPassword: { go(.reset) }
                )

            case .signup:
                SignupView(
                    onSignIn: { go(.login) },
                    onRegistered: { email, password, token in
                        activeEmail = email
                        pendingPassword = password
                        devToken = token
                        go(.verify)
                    }
                )

            case .verify:
                VerifyView(
                    email: activeEmail,
                    devToken: devToken,
                    onVerified: confirmAndEnter,
                    onUseDifferentEmail: { go(.signup) }
                )

            case .reset:
                ResetView(
                    email: activeEmail,
                    onUpdated: { go(.login) },
                    onBackToSignIn: { go(.login) }
                )
            }
        }
        .transition(.opacity.combined(with: .move(edge: .trailing)))
        .animation(.easeInOut(duration: 0.28), value: screen)
    }

    private func go(_ next: AuthScreen) {
        screen = next
    }

    /// Sign in once the address is confirmed, so "Confirm email & continue" lands in
    /// the app rather than back on the login screen.
    private func confirmAndEnter() {
        guard !pendingPassword.isEmpty else {
            go(.login)
            return
        }
        Task {
            await session.signIn(email: activeEmail, password: pendingPassword, remember: true)
            // If that failed the session stays signed out and RootView keeps showing
            // this flow; the error is surfaced by LoginView on the next attempt.
            pendingPassword = ""
            go(.login)
        }
    }
}
