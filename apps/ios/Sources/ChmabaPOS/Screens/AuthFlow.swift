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
    @State private var providerNotice: String?

    // WHY APPLE AND GOOGLE ARE NOT WIRED
    //
    // Sign in with Apple has NOTHING behind it. There is no /auth/apple endpoint
    // (grep the API for "apple" and the only hits are unrelated), no `apple_sub`
    // column on User (models.py:28 has google_sub and nothing equivalent), and no
    // Apple client id in config.py. It needs a model column, a migration, and an
    // endpoint that verifies Apple's identity token -- backend work first. The
    // `com.apple.developer.applesignin` entitlement is also not available to a free
    // personal team, so it likely needs the paid Developer Program.
    //
    // Google is closer but still not reachable from the device. POST /auth/google
    // exists and accepts an `id_token`, which IS the native flow -- but it verifies
    // that token against the single `google_client_id` (config.py:36), and that is the
    // WEB client. A native iOS Google sign-in issues a token whose audience is the iOS
    // client id, so verification would fail. It needs a Google iOS OAuth client, the
    // backend to accept that audience, and the GoogleSignIn SDK added to the app.
    //
    // Neither can be faked, so both buttons say what is missing instead of appearing
    // broken.

    var body: some View {
        ZStack {
            switch screen {
            case .login:
                LoginView(
                    onSignUp: { go(.signup) },
                    onForgotPassword: { go(.reset) },
                    onProviderUnavailable: { provider in
                        providerNotice = "\(provider) is not enabled yet — it needs backend support first. Use email and password."
                    }
                )

            case .signup:
                SignupView(
                    onSignIn: { go(.login) },
                    onRegistered: { email, password, token in
                        activeEmail = email
                        pendingPassword = password
                        devToken = token
                        go(.verify)
                    },
                    onProviderUnavailable: { provider in
                        providerNotice = "\(provider) is not enabled yet — it needs backend support first. Use email and password."
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
        .alert("Not available yet", isPresented: Binding(
            get: { providerNotice != nil },
            set: { if !$0 { providerNotice = nil } }
        )) {
            Button("OK", role: .cancel) { providerNotice = nil }
        } message: {
            Text(providerNotice ?? "")
        }
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
