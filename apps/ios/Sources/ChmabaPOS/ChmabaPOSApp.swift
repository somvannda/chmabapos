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

/// Chooses the root surface.
///
/// The splash is a real gate rather than a fixed delay: the session restore runs
/// concurrently, and we leave the splash when BOTH the three stages have played and
/// the restore has settled. That keeps the prototype's flow without making a fast
/// connection wait out a timer that exists for its own sake.
struct RootView: View {
    @EnvironmentObject private var session: Session
    @State private var splashFinished = false
    // Defaults to Light: the prototype and Android both render light, so following the
    // device was opening the app dark and breaking parity.
    @AppStorage(AppAppearance.storageKey) private var appearanceRaw = AppAppearance.light.rawValue

    var body: some View {
        Group {
            if !splashFinished || session.state == .checking {
                SplashView { splashFinished = true }
            } else {
                switch session.state {
                case .signedIn:
                    ShellView()
                default:
                    AuthFlowView()
                }
            }
        }
        .preferredColorScheme(AppAppearance(rawValue: appearanceRaw)?.colorScheme)
    }
}

/// The three-stage splash, ported from `data-screen="splash" / "splash-2" /
/// "splash-3"` in apps/android/prototype/mobile-ui.html.
///
/// Stage timings are the prototype's own 1500 ms each. The dark field, the
/// decorative rings and every string and size come from its CSS.
struct SplashView: View {
    let onFinished: () -> Void

    @State private var stage = 0
    @State private var sweeping = false

    private static let stageMillis: UInt64 = 1_500_000_000

    var body: some View {
        ZStack {
            ChmabaColor.inkStrong.ignoresSafeArea()

            Group {
                switch stage {
                case 0: stageBrand
                case 1: stagePromise
                default: stageLoading
                }
            }
            .transition(.opacity.combined(with: .scale(scale: 0.96)))
        }
        .task {
            for next in 1...2 {
                try? await Task.sleep(nanoseconds: Self.stageMillis)
                withAnimation(.easeInOut(duration: 0.3)) { stage = next }
            }
            try? await Task.sleep(nanoseconds: Self.stageMillis)
            onFinished()
        }
    }

    // MARK: Stage 1 — brand (data-screen="splash")

    private var stageBrand: some View {
        ZStack {
            // .r1  right -70, top 80, 230x230, 34px ring rgba(105,87,245,.25)
            ring(diameter: 230, lineWidth: 34, colour: ChmabaColor.purple.opacity(0.25))
                .offset(x: 115, y: -140)

            // .r2  left -80, bottom -90, 250x250, rgba(196,242,124,.1), blur 28
            Circle()
                .fill(ChmabaColor.lime.opacity(0.10))
                .frame(width: 250, height: 250)
                .blur(radius: 28)
                .offset(x: -125, y: 145)

            VStack(spacing: 18) {
                brandImage("chmaba-mark")
                    .resizable().interpolation(.high)
                    .frame(width: 56, height: 56)

                Text("chmaba")
                    .font(.system(size: 30, weight: .heavy))
                    .tracking(-0.055)
                    .foregroundStyle(.white)

                Text("Your store, in a better flow.")
                    .font(.system(size: 12))
                    .foregroundStyle(Color(hex: 0xA9AAB2))
            }
        }
    }

    // MARK: Stage 2 — promise (data-screen="splash-2")

    private var stagePromise: some View {
        ZStack {
            // .r3  left -40, top -60, 200x200, 26px ring rgba(196,242,124,.12)
            ring(diameter: 200, lineWidth: 26, colour: ChmabaColor.lime.opacity(0.12))
                .offset(x: -100, y: -160)

            ring(diameter: 230, lineWidth: 34, colour: ChmabaColor.purple.opacity(0.25))
                .offset(x: 115, y: -140)

            VStack(spacing: 0) {
                Text("Built for busy counters")
                    .font(.system(size: 11, weight: .heavy))
                    .tracking(1.76)                     // .16em
                    .textCase(.uppercase)
                    .foregroundStyle(ChmabaColor.lime)

                Text("One workspace.\nEvery moving part.")
                    .font(.system(size: 26, weight: .heavy))
                    .tracking(-0.055)
                    .multilineTextAlignment(.center)
                    .lineSpacing(2)
                    .foregroundStyle(.white)
                    .padding(.top, 14)
                    .padding(.bottom, 10)

                Text("Sales, stock and your whole team in one calm place.")
                    .font(.system(size: 12))
                    .foregroundStyle(Color(hex: 0xA9AAB2))
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
                    .frame(maxWidth: 260)

                HStack(spacing: 18) {
                    featureMark("cart", "Fast sales entry")
                    featureMark("shippingbox", "Live inventory")
                    featureMark("chart.bar", "Clear reports")
                }
                .padding(.top, 22)
            }
        }
    }

    private func featureMark(_ symbol: String, _ label: String) -> some View {
        VStack(spacing: 7) {
            Image(systemName: symbol)
                .font(.system(size: 20))
                .foregroundStyle(ChmabaColor.lime)
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(Color(hex: 0xA9AAB2))
                .multilineTextAlignment(.center)
        }
        .frame(width: 76)
    }

    // MARK: Stage 3 — loading (data-screen="splash-3")

    private var stageLoading: some View {
        ZStack {
            Circle()
                .fill(ChmabaColor.lime.opacity(0.10))
                .frame(width: 250, height: 250)
                .blur(radius: 28)
                .offset(x: -125, y: 145)

            VStack(spacing: 14) {
                brandImage("chmaba-mark")
                    .resizable().interpolation(.high)
                    .frame(width: 44, height: 44)

                Text("Preparing your workspace…")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color(hex: 0xE4E4E8))

                // .bar — 132x3 radius 99 on rgba(255,255,255,.16), with a 40% lime
                // element sweeping from translateX(-100%) to translateX(330%) over
                // 1.9s ease-in-out, forever. Previously this was a static bar, which is
                // why it read as frozen rather than loading.
                Capsule()
                    .fill(Color.white.opacity(0.16))
                    .frame(width: 132, height: 3)
                    .overlay(alignment: .leading) {
                        Capsule()
                            .fill(ChmabaColor.lime)
                            .frame(width: 53, height: 3)
                            .offset(x: sweeping ? 174 : -53)
                            .animation(
                                .easeInOut(duration: 1.9).repeatForever(autoreverses: false),
                                value: sweeping
                            )
                    }
                    .clipShape(Capsule())
                    .padding(.top, 8)
                    .onAppear { sweeping = true }

                Text("Checking your session and loading Main Counter")
                    .font(.system(size: 10.5))
                    .foregroundStyle(Color(hex: 0x6F7078))
            }
        }
    }

    private func ring(diameter: CGFloat, lineWidth: CGFloat, colour: Color) -> some View {
        Circle()
            .strokeBorder(colour, lineWidth: lineWidth)
            .frame(width: diameter, height: diameter)
    }
}
