import SwiftUI

/// Settings, ported from `apps/android/.../screens/settings/SettingsScreen.kt`.
///
/// This screen deliberately asserts no values. The rows under Store and Selling describe
/// what the *web* app owns — the Android client's own comment records that it used to print
/// a tax rate, a receipt width and hardware states that nothing on the device had measured.
/// A number shown here would be a guess dressed as a reading, so Tax and Currency read
/// "Set in the web app" instead.
///
/// "In your plan" lists the keys from `/workspaces/current` rather than offering switches:
/// a plan is changed through billing, not from a POS, and switches here changed nothing.
struct SettingsView: View {
    @EnvironmentObject private var session: Session

    let onBack: () -> Void
    /// Rows that describe web-owned sections report their title so the shell can say where
    /// to change them, instead of doing nothing when tapped.
    let onOpenSection: (String) -> Void

    private struct SettingsRow: Identifiable {
        let id = UUID()
        let title: String
        let subtitle: String
        let icon: ChmabaIcon
        var status: String?
        var tone: BadgeTone = .neutral
    }

    private var storeRows: [SettingsRow] {
        [
            SettingsRow(title: "Store details", subtitle: "Name, address, receipts", icon: .store),
            SettingsRow(title: "Currency & exchange rates", subtitle: "Set in the web app", icon: .dollar),
            SettingsRow(title: "Tax", subtitle: "Set in the web app", icon: .receipt),
        ]
    }

    private var sellingRows: [SettingsRow] {
        [
            SettingsRow(title: "Payment methods", subtitle: "Set in the web app", icon: .creditCard),
            SettingsRow(title: "Receipts & printing", subtitle: "Set in the web app", icon: .printer),
            SettingsRow(title: "Customer display", subtitle: "Set in the web app", icon: .monitor),
        ]
    }

    /// What this app can and cannot reach on the device. Camera scanning is real; there is
    /// no printer or cash-drawer support, so neither offers a status or a Pair button.
    private var hardwareRows: [SettingsRow] {
        [
            SettingsRow(title: "Receipt printer", subtitle: "Not supported in this app yet", icon: .printer),
            SettingsRow(
                title: "Barcode scanner",
                subtitle: "Uses the device camera",
                icon: .scan,
                status: "Ready",
                tone: .green
            ),
            SettingsRow(title: "Cash drawer", subtitle: "Not supported in this app yet", icon: .wallet),
        ]
    }

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 12) { content }
        }
        .background(ChmabaColor.background)
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Settings")
                    .font(.system(size: 20, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                Text(session.workspaceName ?? "Your store")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        sectionHeading("Store")
        group(storeRows, tappable: true)

        sectionHeading("Selling")
        group(sellingRows, tappable: true)

        if !session.capabilities.isEmpty {
            sectionHeading("Feature packs")
            featurePacksPanel
        }

        sectionHeading("In your plan")
        planPanel

        sectionHeading("Hardware")
        group(hardwareRows, tappable: true)

        ChmabaButton(
            text: "Sign out",
            variant: .danger,
            size: .large,
            fullWidth: true
        ) {
            Task { await session.signOut() }
        }
        .padding(.top, 18)
        .padding(.bottom, 8)
    }

    private var featurePacksPanel: some View {
        PanelList {
            ForEach(Array(session.capabilities.enumerated()), id: \.element) { index, pack in
                ListRow(showsDivider: index < session.capabilities.count - 1) {
                    AnyView(
                        HStack(spacing: 12) {
                            RoundedRectangle(cornerRadius: 11, style: .continuous)
                                .fill(ChmabaColor.lavender)
                                .frame(width: 34, height: 34)
                                .overlay {
                                    ChmabaIconView(icon: .check, size: 17, color: ChmabaColor.purple)
                                }
                            // The store's own packs, straight from /workspaces/current.
                            // Read-only: an owner changes packs in the web app.
                            Text(Self.humanised(pack))
                                .font(.system(size: 12.5, weight: .semibold))
                                .foregroundStyle(ChmabaColor.textPrimary)
                                .lineLimit(1)
                        }
                    )
                } trailing: {
                    EmptyView()
                } action: {
                    // Nothing to open: packs are changed in the web app.
                }
            }
        }
        .padding(.bottom, 4)
    }

    private var planPanel: some View {
        PanelList {
            if session.planFeatures.isEmpty {
                noticeLine("No features are enabled for this plan.")
                    .padding(16)
            } else {
                ForEach(Array(session.planFeatures.enumerated()), id: \.element) { index, feature in
                    ListRow(showsDivider: index < session.planFeatures.count - 1) {
                        AnyView(
                            HStack(spacing: 12) {
                                RoundedRectangle(cornerRadius: 11, style: .continuous)
                                    .fill(ChmabaColor.lavender)
                                    .frame(width: 34, height: 34)
                                    .overlay {
                                        ChmabaIconView(icon: .check, size: 17, color: ChmabaColor.purple)
                                    }
                                // Taken from the workspace's own plan_features, so the list
                                // tracks the server without a second copy of the feature
                                // catalogue living in the app.
                                Text(Self.humanised(feature))
                                    .font(.system(size: 12.5, weight: .semibold))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                    .lineLimit(1)
                            }
                        )
                    } trailing: {
                        EmptyView()
                    } action: {
                        // Nothing to open: a plan changes through billing.
                    }
                }
            }
        }
        .padding(.bottom, 4)
    }

    private func group(_ rows: [SettingsRow], tappable: Bool) -> some View {
        PanelList {
            ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                ListRow(showsDivider: index < rows.count - 1) {
                    AnyView(
                        HStack(spacing: 12) {
                            RoundedRectangle(cornerRadius: 11, style: .continuous)
                                .fill(ChmabaColor.lavender)
                                .frame(width: 34, height: 34)
                                .overlay {
                                    ChmabaIconView(icon: row.icon, size: 17, color: ChmabaColor.purple)
                                }
                            VStack(alignment: .leading, spacing: 2) {
                                Text(row.title)
                                    .font(.system(size: 12.5, weight: .bold))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                    .lineLimit(1)
                                Text(row.subtitle)
                                    .font(.system(size: 10))
                                    .foregroundStyle(ChmabaColor.faint)
                                    .lineLimit(1)
                            }
                        }
                    )
                } trailing: {
                    if let status = row.status {
                        ChmabaBadge(text: status, tone: row.tone)
                    } else {
                        EmptyView()
                    }
                } action: {
                    if tappable { onOpenSection(row.title) }
                }
            }
        }
        .padding(.bottom, 4)
    }

    private func sectionHeading(_ text: String) -> some View {
        Text(text.uppercased())
            .font(.system(size: 9.5, weight: .bold))
            .tracking(0.6)
            .foregroundStyle(ChmabaColor.faint)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 14)
            .padding(.bottom, 6)
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 10.5))
            .foregroundStyle(ChmabaColor.faint)
    }

    /// `advanced_reports` reads as "Advanced reports".
    static func humanised(_ feature: String) -> String {
        let spaced = feature.replacingOccurrences(of: "_", with: " ")
        guard let first = spaced.first else { return spaced }
        return String(first).uppercased() + spaced.dropFirst()
    }
}
