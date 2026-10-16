import SwiftUI

/// Onboarding — the four steps from the prototype's `setup-company`, `setup-questions`,
/// `setup-plan` and `setup-ready`.
///
/// This exists because a newly registered account has no company and no store:
/// `GET /workspaces/current` answers **403 "Set up a workspace before using this feature"**,
/// and there was no way past it. Without this screen a new customer could sign in and reach
/// nothing, which is the largest gap the iOS client had.
///
/// All four steps submit once, at the end, through `POST /workspaces/setup` — which creates
/// the company, the store and the owner membership together and returns the new workspace.
/// Nothing is created until the last step, so abandoning onboarding leaves no half-built
/// company behind.
struct OnboardingView: View {
    @EnvironmentObject private var session: Session

    @State private var step = 0
    @State private var companyName = ""
    @State private var storeName = ""
    @State private var country = "Cambodia"
    @State private var currencyCode = "USD"
    @State private var vertical = "general"
    @State private var selectedPlan = "free"
    @State private var billingCycle: BillingCycle = .monthly
    @State private var plans: [PlanRead] = []
    @State private var currencies: [CurrencyRead] = []
    @State private var submitting = false
    @State private var error: String?

    /// The shared country list from `apps/web/src/lib/countries.js`, kept in step with it
    /// rather than invented here: `Company.country` is a free-text column seeded with these
    /// names, not ISO codes, so the two lists must not drift.
    private static let countries = [
        "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
        "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain",
        "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
        "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria",
        "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada",
        "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros",
        "Congo", "Costa Rica", "Côte d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia",
        "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica",
        "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea",
        "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France",
        "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada",
        "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary",
        "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy",
        "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kuwait",
        "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya",
        "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia",
        "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius",
        "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco",
        "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands",
        "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia",
        "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea",
        "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania",
        "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia",
        "Saint Vincent and the Grenadines", "Samoa", "San Marino",
        "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles",
        "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia",
        "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan",
        "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania",
        "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia",
        "Türkiye", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine",
        "United Arab Emirates", "United Kingdom", "United States", "Uruguay",
        "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen",
        "Zambia", "Zimbabwe",
    ]

    private var canContinueCompany: Bool {
        companyName.trimmingCharacters(in: .whitespacesAndNewlines).count >= 2
            && storeName.trimmingCharacters(in: .whitespacesAndNewlines).count >= 2
    }

    /// Live from `GET /currencies`, so the menu follows the server's active set rather than a
    /// hard-coded trio. The fallback exists only so a failed call shows a usable menu instead
    /// of an empty one; the API rejects an unsupported currency either way.
    private var currencyOptions: [(String, String)] {
        guard !currencies.isEmpty else {
            return [("USD", "USD - US Dollar"), ("KHR", "KHR - Cambodian Riel"),
                    ("THB", "THB - Thai Baht")]
        }
        return currencies.map { ($0.code, "\($0.code) - \($0.name)") }
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            PageBody(topPadding: 0) {
                switch step {
                case 0: companyStep
                case 1: questionsStep
                case 2: planStep
                default: readyStep
                }
            }
        }
        .background(ChmabaColor.background)
        .task {
            // Both lists are public, so the pricing and the currency menu can fill in before
            // the workspace exists. Failure is not fatal: the pickers fall back.
            if plans.isEmpty {
                plans = (try? await APIClient.shared.get("plans", as: [PlanRead].self)) ?? []
            }
            if currencies.isEmpty {
                currencies = (try? await APIClient.shared.get(
                    "currencies", as: [CurrencyRead].self
                )) ?? []
            }
        }
    }

    // MARK: Header

    private var header: some View {
        VStack(spacing: 0) {
            HStack {
                Text("chmaba")
                    .font(.system(size: 16, weight: .heavy))
                    .foregroundStyle(ChmabaColor.textPrimary)
                Spacer(minLength: 0)
                ChmabaBadge(text: "Step \(step + 1) of 4", tone: .violet)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)

            // The prototype's `.track`, filled a quarter per step.
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(ChmabaColor.surfaceVariant)
                    Capsule()
                        .fill(ChmabaColor.purple)
                        .frame(width: geo.size.width * (Double(step + 1) / 4.0))
                        .animation(.easeInOut(duration: 0.28), value: step)
                }
            }
            .frame(height: 4)
            .padding(.horizontal, 16)
        }
    }

    // MARK: Step 1 — company

    private var companyStep: some View {
        VStack(alignment: .leading, spacing: 0) {
            title("Tell us about your store", "This appears on your receipts and reports.")
            field("Company name", text: $companyName, placeholder: "Cedar & Stone")
            field("Store name", text: $storeName, placeholder: "Main Counter")

            HStack(spacing: 10) {
                picker("Country", selection: $country,
                       options: Self.countries.map { ($0, $0) })
                picker("Default currency", selection: $currencyCode, options: currencyOptions)
            }

            if let error { errorLine(error) }

            ChmabaButton(text: "Continue", variant: .primary, size: .large,
                         enabled: canContinueCompany, fullWidth: true) {
                step = 1
            }
            .padding(.top, 16)
        }
    }

    // MARK: Step 2 — business type

    private var questionsStep: some View {
        VStack(alignment: .leading, spacing: 0) {
            title("What kind of store?", "We switch on the right feature packs for you.")

            VStack(spacing: 8) {
                ForEach(BusinessType.all) { type in
                    Button {
                        vertical = type.code
                    } label: {
                        HStack(spacing: 11) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(type.name)
                                    .font(.system(size: 12.5, weight: .bold))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                Text(type.detail)
                                    .font(.system(size: 10))
                                    .foregroundStyle(ChmabaColor.faint)
                            }
                            Spacer(minLength: 0)
                            if vertical == type.code {
                                ChmabaIconView(icon: .check, size: 14, color: ChmabaColor.purple)
                            }
                        }
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 14))
                    .overlay {
                        RoundedRectangle(cornerRadius: 14)
                            .strokeBorder(vertical == type.code ? ChmabaColor.purple
                                                                : ChmabaColor.border,
                                          lineWidth: vertical == type.code ? 1.5 : 1)
                    }
                }
            }

            ChmabaButton(text: "Continue", variant: .primary, size: .large, fullWidth: true) {
                step = 2
            }
            .padding(.top, 16)
        }
    }

    // MARK: Step 3 — plan

    private var planStep: some View {
        VStack(alignment: .leading, spacing: 0) {
            title("Choose a plan", "Start free. Upgrade when your store is ready.")

            Text("Billing cycle")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
                .padding(.bottom, 8)

            VStack(spacing: 8) {
                ForEach(BillingCycle.allCases) { entry in
                    Button {
                        billingCycle = entry
                    } label: {
                        HStack(spacing: 11) {
                            ZStack {
                                Circle()
                                    .fill(entry == billingCycle ? ChmabaColor.purple : .clear)
                                    .frame(width: 18, height: 18)
                                if entry == billingCycle {
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
            }

            if !plans.isEmpty {
                Text("Choose a plan")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(ChmabaColor.textSecondary)
                    .padding(.top, 16)
                    .padding(.bottom, 8)

                VStack(spacing: 8) {
                    ForEach(plans) { plan in
                        Button {
                            selectedPlan = plan.code
                        } label: {
                            HStack(spacing: 11) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(plan.name)
                                        .font(.system(size: 12.5, weight: .heavy))
                                        .foregroundStyle(ChmabaColor.textPrimary)
                                    Text(plan.priceLabel(billingCycle) + (plan.isFree() ? "" : " /mo"))
                                        .font(.system(size: 11))
                                        .foregroundStyle(ChmabaColor.muted)
                                }
                                Spacer(minLength: 0)
                                if selectedPlan == plan.code {
                                    ChmabaIconView(icon: .check, size: 14, color: ChmabaColor.purple)
                                }
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(
                            plan.code == plans.featuredCode ? ChmabaColor.lime : ChmabaColor.surface,
                            in: RoundedRectangle(cornerRadius: 14)
                        )
                    }
                }
            }

            if let error { errorLine(error) }

            let chosen = plans.first { $0.code == selectedPlan }
            ChmabaButton(
                text: chosen == nil ? "Create my workspace" : "Continue with \(chosen!.name)",
                variant: .primary,
                size: .large,
                enabled: !submitting,
                fullWidth: true,
                loading: submitting
            ) {
                Task { await submit() }
            }
            .padding(.top, 16)
        }
    }

    // MARK: Step 4 — ready

    private var readyStep: some View {
        VStack(spacing: 0) {
            ZStack {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(BadgeTone.green.background)
                    .frame(width: 64, height: 64)
                ChmabaIconView(icon: .sparkles, size: 28, color: BadgeTone.green.foreground)
            }
            .padding(.top, 40)

            Text("You're ready")
                .font(.system(size: 26, weight: .heavy))
                .tracking(-0.05)
                .foregroundStyle(ChmabaColor.textPrimary)
                .padding(.top, 20)

            Text("\(storeName) is set up. Take your first sale, or add products first.")
                .font(.system(size: 11.5))
                .lineSpacing(2)
                .multilineTextAlignment(.center)
                .foregroundStyle(ChmabaColor.muted)
                .padding(.top, 8)

            ChmabaButton(text: "Open the register", variant: .primary, size: .large, fullWidth: true) {
                // This is the moment the workspace becomes the session, which is what makes
                // RootView swap onboarding for the shell.
                Task { await session.refreshWorkspace() }
            }
            .padding(.top, 22)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: Pieces

    private func title(_ main: String, _ sub: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(main)
                .font(.system(size: 20, weight: .heavy))
                .tracking(-0.05)
                .foregroundStyle(ChmabaColor.textPrimary)
            Text(sub)
                .font(.system(size: 11))
                .foregroundStyle(ChmabaColor.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.bottom, 16)
    }

    private func field(_ label: String, text: Binding<String>, placeholder: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            TextField(placeholder, text: text)
                .font(.system(size: 13))
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
        }
        .padding(.bottom, 12)
    }

    private func picker(_ label: String, selection: Binding<String>,
                        options: [(String, String)]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            Menu {
                ForEach(options, id: \.0) { value, title in
                    Button(title) { selection.wrappedValue = value }
                }
            } label: {
                HStack {
                    Text(options.first { $0.0 == selection.wrappedValue }?.1 ?? selection.wrappedValue)
                        .font(.system(size: 12.5))
                        .foregroundStyle(ChmabaColor.textPrimary)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    ChmabaIconView(icon: .chevronDown, size: 12, color: ChmabaColor.faint)
                }
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 12)
    }

    private func errorLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .lineSpacing(2)
            .foregroundStyle(BadgeTone.red.foreground)
            .fixedSize(horizontal: false, vertical: true)
            .padding(.top, 8)
    }

    // MARK: Submit

    private func submit() async {
        submitting = true
        error = nil
        let payload = WorkspaceSetupRequest(
            companyName: companyName.trimmingCharacters(in: .whitespacesAndNewlines),
            storeName: storeName.trimmingCharacters(in: .whitespacesAndNewlines),
            country: country,
            currencyCode: currencyCode,
            vertical: vertical,
            planCode: selectedPlan,
            billingCycle: billingCycle.rawValue
        )
        do {
            _ = try await APIClient.shared.post(
                "workspaces/setup", body: payload, as: WorkspaceRead.self
            )
            // Deliberately NOT refreshing the session here. `storeId` becoming non-nil is what
            // tells RootView to show the shell, so refreshing now would swap the screen out
            // from under the "You're ready" step. The ready step refreshes on its own button.
            step = 3
        } catch let apiError as APIError {
            error = apiError.errorDescription
            // A 409 means the account already has a workspace -- possibly from an earlier
            // attempt that succeeded after the app was closed. Adopt it rather than leaving
            // the merchant on a form that can never succeed.
            await session.refreshWorkspace()
            if session.storeId != nil {
                error = nil
                step = 3
            }
        } catch {
            self.error = "Could not set up the workspace."
        }
        submitting = false
    }
}
