import SwiftUI

/// Billing & plans — live platform pricing. Ported from
/// `apps/android/.../screens/plans/PlansScreen.kt`, which is the Android client's screen for
/// this destination.
///
/// Reads the public `GET /plans`, which needs no token.
///
/// The price maths is deliberately identical to the web and Android: a per-month figure
/// discounted by the cycle, and a total for the whole period. Drift here would quote one
/// customer two different prices on two clients, which is why the Android client keeps a
/// parity test against the web and why this file follows it rather than inventing anything.
///
/// Currency is dollars and deliberately not the store's own: `PlanRead` carries a bare
/// `monthly_price` with no currency at all, and the web renders it through a helper named
/// `moneyUsd`. Billing a riel shop's subscription in riel would be wrong.
struct PlansView: View {
    let onBack: () -> Void
    /// Choosing a plan needs the billing checkout, which is not built. The shell reports
    /// that rather than leaving the button inert.
    let onChoosePlan: (String) -> Void

    @State private var plans: [PlanRead] = []
    @State private var cycle: BillingCycle = .monthly
    @State private var selectedCode: String?
    /// Which card the carousel has settled on, written by `scrollPosition`.
    @State private var visibleCode: String?
    @State private var loading = true
    @State private var error: String?

    // The lime "most popular" card's own palette, taken from the Android screen rather than
    // bent out of the shared tokens.
    private let limeInk = Color(hex: 0x172015)
    private let limeMuted = Color(hex: 0x40522F)
    private let limeBody = Color(hex: 0x3E5130)
    private let limeCheck = Color(hex: 0x4D7835)
    private let chmabaGreen = Color(hex: 0x4CAF50)

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 4) { content }
        }
        .background(ChmabaColor.background)
        .task { await load() }
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Plans")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Live pricing from Chmaba.")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer(minLength: 0)
                IconButton(icon: .refresh) { Task { await load() } }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        if loading {
            noticeLine("Loading plans…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if plans.isEmpty {
            noticeLine("No plans are available right now.")
        } else {
            sectionLabel("Billing cycle")
            VStack(spacing: 8) {
                ForEach(BillingCycle.allCases) { entry in
                    cycleRow(entry)
                }
            }

            sectionLabel("Choose a plan")

            // The prototype's peeking carousel. Cards are 84% wide so the next one shows at
            // the right edge -- that peek is the affordance that says "these swipe", which is
            // why there are no arrow buttons. One index drives the cards, the dots, the
            // counter and the CTA, so the button always names whatever card is showing.
            HStack {
                Text("Swipe to compare")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(ChmabaColor.textSecondary)
                Spacer(minLength: 0)
                Text("\(visibleIndex + 1) / \(plans.count)")
                    .font(.system(size: 10))
                    .foregroundStyle(ChmabaColor.faint)
            }
            .padding(.bottom, 8)

            ScrollView(.horizontal) {
                HStack(spacing: 12) {
                    ForEach(plans) { plan in
                        planCard(plan)
                            .containerRelativeFrame(.horizontal) { length, _ in length * 0.84 }
                            .id(plan.code)
                    }
                }
                .scrollTargetLayout()
            }
            .scrollIndicators(.hidden)
            .scrollTargetBehavior(.viewAligned)
            .scrollPosition(id: $visibleCode)
            .padding(.horizontal, -2)

            HStack(spacing: 6) {
                ForEach(plans) { plan in
                    Capsule()
                        .fill(plan.code == activeCode ? ChmabaColor.purple : ChmabaColor.border)
                        .frame(width: plan.code == activeCode ? 18 : 6, height: 6)
                        .animation(.easeInOut(duration: 0.28), value: activeCode)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.top, 12)

            let chosen = plans.first { $0.code == activeCode }
            ChmabaButton(
                text: chosen == nil ? "Choose a plan" : "Continue with \(chosen!.name)",
                variant: .primary,
                size: .large,
                enabled: chosen != nil,
                fullWidth: true
            ) {
                if let code = chosen?.code { onChoosePlan(code) }
            }
            .padding(.top, 12)
        }
    }

    /// Whichever card the carousel is showing: the scrolled-to one, else the tapped one,
    /// else the first. Everything that must agree with the visible card reads this.
    private var activeCode: String? {
        visibleCode ?? selectedCode ?? plans.first?.code
    }

    private var visibleIndex: Int {
        guard let code = activeCode,
              let index = plans.firstIndex(where: { $0.code == code }) else { return 0 }
        return index
    }

    private func cycleRow(_ entry: BillingCycle) -> some View {
        let active = entry == cycle
        return Button {
            cycle = entry
        } label: {
            HStack(spacing: 11) {
                ZStack {
                    Circle()
                        .fill(active ? ChmabaColor.purple : Color.clear)
                        .frame(width: 18, height: 18)
                    if active {
                        ChmabaIconView(icon: .check, size: 11, color: .white)
                    }
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(entry.label)
                        .font(.system(size: 12.5, weight: .bold))
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text(entry.billedLabel)
                        .font(.system(size: 10.5))
                        .foregroundStyle(ChmabaColor.faint)
                }
                Spacer(minLength: 0)
                if let badge = entry.badge {
                    ChmabaBadge(text: badge, tone: .green)
                }
            }
            .padding(.horizontal, 13)
            .padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 13))
    }

    private func planCard(_ plan: PlanRead) -> some View {
        let featured = plan.code == plans.featuredCode
        let active = plan.code == activeCode
        let titleColor = featured ? limeMuted : ChmabaColor.purple
        let bodyColor = featured ? limeBody : ChmabaColor.faint
        let priceColor = featured ? limeInk : ChmabaColor.textPrimary

        return Button {
            selectedCode = plan.code
        } label: {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 8) {
                    Text(plan.name)
                        .font(.system(size: 12.5, weight: .heavy))
                        .foregroundStyle(titleColor)
                    if featured {
                        Text("MOST POPULAR")
                            .font(.system(size: 8.5, weight: .heavy))
                            .foregroundStyle(ChmabaColor.lime)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(ChmabaColor.inkStrong, in: Capsule())
                    }
                    Spacer(minLength: 0)
                    ZStack {
                        Circle()
                            .fill(active ? (featured ? ChmabaColor.inkStrong : ChmabaColor.purple)
                                         : Color.clear)
                            .frame(width: 20, height: 20)
                        if active {
                            ChmabaIconView(
                                icon: .check,
                                size: 12,
                                color: featured ? ChmabaColor.lime : .white
                            )
                        }
                    }
                }

                HStack(alignment: .lastTextBaseline, spacing: 4) {
                    Text(plan.priceLabel(cycle))
                        .font(.system(size: 30, weight: .heavy))
                        .tracking(-0.06)
                        .foregroundStyle(priceColor)
                    if !plan.isFree() {
                        Text("/mo")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(bodyColor)
                    }
                }
                .padding(.top, 10)

                if let total = plan.totalFor(cycle) {
                    Text("$\(total) \(cycle.billedLabel)")
                        .font(.system(size: 10))
                        .foregroundStyle(bodyColor)
                        .padding(.top, 3)
                }

                if let description = plan.description, !description.isEmpty {
                    Text(description)
                        .font(.system(size: 11))
                        .lineSpacing(2)
                        .foregroundStyle(bodyColor)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 6)
                }

                if !plan.marketingFeatures.isEmpty {
                    VStack(alignment: .leading, spacing: 7) {
                        ForEach(plan.marketingFeatures, id: \.self) { feature in
                            HStack(alignment: .top, spacing: 8) {
                                ChmabaIconView(
                                    icon: .check,
                                    size: 14,
                                    color: featured ? limeCheck : chmabaGreen
                                )
                                Text(feature)
                                    .font(.system(size: 11.5))
                                    .lineSpacing(2)
                                    .foregroundStyle(featured ? limeBody : ChmabaColor.muted)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(.top, 12)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .background(
            featured ? ChmabaColor.lime : ChmabaColor.surface,
            in: RoundedRectangle(cornerRadius: 16)
        )
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 12.5, weight: .bold))
            .foregroundStyle(ChmabaColor.textPrimary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 10)
            .padding(.bottom, 8)
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    private func load() async {
        if plans.isEmpty { loading = true }
        error = nil
        do {
            plans = try await APIClient.shared.get("plans", as: [PlanRead].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load plans."
            loading = false
        }
    }
}
