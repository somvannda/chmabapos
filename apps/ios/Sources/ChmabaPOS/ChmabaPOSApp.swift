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

/// Shown while we attempt a silent session restore. Matches the Android splash's
/// visual language (brand mark on the brand colour) without its fixed 3-stage timer
/// -- here we are waiting on a real network call, not a cosmetic delay.
struct SplashView: View {
    var body: some View {
        ZStack {
            ChmabaColor.purple.ignoresSafeArea()
            VStack(spacing: Spacing.md) {
                ChmabaLogo(size: 64)
                Text("Chmaba Cloud POS")
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(.white)
                ProgressView()
                    .tint(ChmabaColor.lime)
                    .padding(.top, Spacing.sm)
            }
        }
    }
}

/// The brand mark: two overlapping rings, matching the web/Android `Logo`.
struct ChmabaLogo: View {
    var size: CGFloat = 40

    var body: some View {
        ZStack {
            Circle()
                .strokeBorder(ChmabaColor.lime, lineWidth: size * 0.09)
                .frame(width: size * 0.72, height: size * 0.72)
                .offset(x: -size * 0.14)
            Circle()
                .strokeBorder(.white, lineWidth: size * 0.09)
                .frame(width: size * 0.72, height: size * 0.72)
                .offset(x: size * 0.14)
        }
        .frame(width: size, height: size)
    }
}
