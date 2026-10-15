import SwiftUI

@main
struct ChmabaPOSApp: App {
    @StateObject private var session = Session()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .task { await session.restore() }
        }
    }
}

/// Chooses the root surface from the session state.
///
/// Kept deliberately simple: the Android client hand-rolls navigation with
/// `mutableStateOf` and a bespoke `BackHandler` unwind (see
/// docs/ios-platform-options.md Appendix B). Here the equivalent is a state enum
/// plus `NavigationStack`, which gives us the unwind behaviour for free.
struct RootView: View {
    @EnvironmentObject private var session: Session

    var body: some View {
        switch session.state {
        case .checking:
            SplashView()
        case .signedOut:
            LoginView()
        case .signedIn:
            POSView()
        }
    }
}

/// Shown while we attempt a silent session restore.
///
/// The Android splash runs three fixed 1500 ms stages; here we are waiting on a real
/// network call instead, so a fixed timer would only add dead time on a fast
/// connection and cut off a slow one.
struct SplashView: View {
    var body: some View {
        ZStack {
            ChmabaColor.purple.ignoresSafeArea()
            VStack(spacing: Spacing.md) {
                ChmabaLogo(chipSize: 64, wordmark: true, onDark: true)
                ProgressView()
                    .tint(ChmabaColor.lime)
                    .padding(.top, Spacing.sm)
            }
        }
    }
}
