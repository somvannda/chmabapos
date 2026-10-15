import SwiftUI

/// The Home tab, ported from `data-screen="dashboard"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /reports/summary`.
///
/// Where the prototype shows a figure the API cannot supply (the week-over-week
/// percentage deltas), the caption is omitted rather than invented -- the same rule
/// the Android client applies when it removes a mock-up figure with no API source.
struct DashboardView: View {
    @EnvironmentObject private var session: Session

    let onOpenMenu: () -> Void
    let onNewSale: () -> Void
    let onOpenProducts: () -> Void
    let onOpenOrders: () -> Void

    @State private var summary: ReportSummary?
    @State private var loading = true
    @State private var error: String?
    @State private var period: DashboardPeriod = .today

    private var storeName: String { session.workspaceName ?? "Your store" }

    private var greeting: String {
        switch Calendar.current.component(.hour, from: Date()) {
        case 0..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        default: return "Good evening"
        }
    }

    private var firstName: String {
        session.user?.fullName.split(separator: " ").first.map(String.init) ?? "there"
    }

    private var currency: String { summary?.currency ?? session.currencyCode }

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 4) { content }
        }
        .background(ChmabaColor.background)
        .task { await load() }
    }

    // MARK: App bar

    private var appBar: some View {
        AppBar {
            AppBarRow(
                leading: { IconButton(icon: .menu, action: onOpenMenu) },
                trailing: {
                    HStack(spacing: 10) {
                        AppearanceToggleButton()
                        IconButton(icon: .bell) { }
                        Circle()
                            .fill(Color(hex: 0xD7C0A2))
                            .frame(width: 36, height: 36)
                            .overlay {
                                Text(initials)
                                    .font(.system(size: 11, weight: .heavy))
                                    .foregroundStyle(Color(hex: 0x44424A))
                            }
                    }
                },
                title: "Dashboard",
                subtitle: "\(storeName) · open",
                live: true
            )
        }
    }

    private var initials: String {
        let parts = (session.user?.fullName ?? "?").split(separator: " ").prefix(2)
        return parts.compactMap { $0.first.map(String.init) }.joined().uppercased()
    }

    // MARK: Body

    @ViewBuilder
    private var content: some View {
        HStack(spacing: 6) {
            Circle().fill(BadgeTone.green.dot).frame(width: 6, height: 6)
            Text(Date().formatted(.dateTime.weekday(.wide).month(.wide).day().year()))
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(ChmabaColor.muted)
        }

        Text("\(greeting), \(firstName).")
            .font(.system(size: 22, weight: .heavy))
            .tracking(-0.05)
            .foregroundStyle(ChmabaColor.textPrimary)
            .padding(.top, 6)

        Text("Here is what is happening at \(storeName) today.")
            .font(.system(size: 12))
            .foregroundStyle(ChmabaColor.muted)

        ChmabaButton(
            text: "New sale", variant: .primary, size: .medium,
            fullWidth: true, leadingIcon: .plus, action: onNewSale
        )
        .padding(.top, 14)
        .padding(.bottom, 12)

        if loading {
            StatGrid {
                ForEach(0..<4, id: \.self) { _ in
                    StatTile(label: "Loading", value: "—", tone: .neutral)
                }
            }
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
        } else if let summary {
            metrics(summary)
            salesOverview(summary)
            topProducts(summary)
            recentTransactions(summary)
        }

        quickActions
    }

    private func metrics(_ summary: ReportSummary) -> some View {
        StatGrid {
            StatTile(
                label: "Net sales",
                value: money(summary.effectiveNet, code: currency),
                detail: "After discounts & refunds",
                tone: .violet
            )
            StatTile(
                label: "Transactions",
                value: "\(summary.transactions)",
                detail: String(format: "%.1f / day", summary.averagePerDay),
                tone: .green
            )
            StatTile(
                label: "Average order",
                value: money(decimal(summary.averageOrder), code: currency),
                detail: "Net per paid order",
                tone: .red
            )
            StatTile(
                label: "Refunds",
                value: money(decimal(summary.refunds), code: currency),
                detail: summary.refundsCount == 1 ? "1 order" : "\(summary.refundsCount) orders",
                tone: .yellow
            )
        }
    }

    private func salesOverview(_ summary: ReportSummary) -> some View {
        POSPanel {
            SectionHeading(title: "Sales overview", subtitle: "Net for the selected period")

            ChipRow(items: DashboardPeriod.allCases, title: \.title, selection: $period)
                .padding(.top, 12)
                .onChange(of: period) { _, _ in Task { await load() } }

            SalesChart(days: summary.dailySales)
                .padding(.top, 14)
        }
        .padding(.top, 12)
    }

    private func topProducts(_ summary: ReportSummary) -> some View {
        POSPanel {
            SectionHeading(
                title: "Top products",
                subtitle: "Best sellers in this period",
                trailing: AnyView(
                    Button("View catalog", action: onOpenProducts)
                        .buttonStyle(.plain)
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(ChmabaColor.muted)
                )
            )

            if summary.topProducts.isEmpty {
                emptyLine("Nothing sold in this period yet.")
            } else {
                let rows = Array(summary.topProducts.prefix(5))
                let peak = max(rows.map(\.value).max() ?? 1, 0.0001)
                VStack(spacing: 10) {
                    ForEach(Array(rows.enumerated()), id: \.offset) { index, item in
                        HStack(spacing: 11) {
                            Text(String(format: "%02d", index + 1))
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(ChmabaColor.faint)
                                .frame(width: 12)
                            MarkChip(text: initials(of: item.displayName), background: palette(index))
                            VStack(alignment: .leading, spacing: 5) {
                                Text(item.displayName)
                                    .font(.system(size: 11, weight: .bold))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                    .lineLimit(1)
                                // Share of the period's top seller, not of all sales:
                                // the API gives per-product amounts, so ranking against
                                // the largest row is the honest reading.
                                ProgressTrack(fraction: item.value / peak)
                            }
                            VStack(alignment: .trailing, spacing: 2) {
                                Text("\(item.units)")
                                    .font(.system(size: 11, weight: .heavy))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                Text("sold")
                                    .font(.system(size: 10))
                                    .foregroundStyle(ChmabaColor.faint)
                            }
                            .frame(width: 40, alignment: .trailing)
                        }
                    }
                }
                .padding(.top, 10)
            }
        }
        .padding(.top, 12)
    }

    private func recentTransactions(_ summary: ReportSummary) -> some View {
        POSPanel(padding: 0) {
            SectionHeading(
                title: "Recent transactions",
                subtitle: "Latest activity at \(storeName)",
                trailing: AnyView(
                    Button("View all", action: onOpenOrders)
                        .buttonStyle(.plain)
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(ChmabaColor.muted)
                )
            )
            .padding(14)

            if summary.transactionsDetail.isEmpty {
                emptyLine("No transactions in this period.")
                    .padding(.horizontal, 16)
                    .padding(.bottom, 14)
            } else {
                let rows = Array(summary.transactionsDetail.prefix(6))
                ForEach(Array(rows.enumerated()), id: \.offset) { index, order in
                    HStack(spacing: 11) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(order.orderNumber ?? "—")
                                .font(.system(size: 12, weight: .heavy))
                                .foregroundStyle(ChmabaColor.textPrimary)
                            Text("\(order.itemsCount) items · \(order.timeLabel)")
                                .font(.system(size: 10))
                                .foregroundStyle(ChmabaColor.faint)
                        }
                        Spacer()
                        ChmabaBadge(text: order.methodLabel, tone: order.badgeTone)
                        Text(money(Decimal(order.totalValue), code: order.currencyCode ?? currency))
                            .font(.system(size: 12, weight: .heavy))
                            .foregroundStyle(ChmabaColor.textPrimary)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 13)
                    .overlay(alignment: .top) {
                        if index > 0 {
                            Rectangle().fill(Color(hex: 0xF2F2F5)).frame(height: 1)
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture(perform: onOpenOrders)
                }
            }
        }
        .padding(.top, 12)
    }

    private var quickActions: some View {
        POSPanel(dark: true) {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Quick actions")
                        .font(.system(size: 10, weight: .heavy))
                        .tracking(1.4)
                        .textCase(.uppercase)
                        .foregroundStyle(ChmabaColor.lime)
                    Text("Keep things moving")
                        .font(.system(size: 14, weight: .heavy))
                        .foregroundStyle(.white)
                }
                Spacer()
                Image(systemName: "sparkles").foregroundStyle(ChmabaColor.lime)
            }

            LazyVGrid(
                columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)],
                spacing: 12
            ) {
                quickAction("plus", "New product")
                quickAction("archivebox", "Adjust stock")
                quickAction("person.badge.plus", "Invite teammate")
                quickAction("chart.bar", "View reports")
            }
            .padding(.top, 14)
        }
        .padding(.top, 12)
    }

    private func quickAction(_ symbol: String, _ label: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: symbol).font(.system(size: 13)).foregroundStyle(ChmabaColor.lime)
            Text(label).font(.system(size: 11)).foregroundStyle(Color(hex: 0xD0D0D5)).lineLimit(1)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12)
        .frame(height: 40)
        .background(Color(hex: 0x222328), in: RoundedRectangle(cornerRadius: 12))
        .overlay {
            RoundedRectangle(cornerRadius: 12).strokeBorder(Color(hex: 0x34353B), lineWidth: 1)
        }
    }

    // MARK: Helpers

    private func emptyLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    private func decimal(_ raw: String?) -> Decimal {
        Decimal(string: raw ?? "0") ?? 0
    }

    private func initials(of name: String) -> String {
        name.split(separator: " ").prefix(2).compactMap { $0.first.map(String.init) }.joined().uppercased()
    }

    private func palette(_ index: Int) -> Color {
        [Color(hex: 0xD7C0A2), Color(hex: 0xB9D7A2), Color(hex: 0xF0C986)][index % 3]
    }

    private func load() async {
        if summary == nil { loading = true }
        error = nil

        // All time has no upper bound; the API takes to_date as optional.
        let report = period.reportPeriod
        var path = "reports/summary?from_date=\(report.from)"
        if let to = report.to { path += "&to_date=\(to)" }

        do {
            summary = try await APIClient.shared.get(path, as: ReportSummary.self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load your numbers."
            loading = false
        }
    }
}

/// `.chart` — bars whose last column is brand purple. 110pt on the Dashboard, 130pt
/// on Reports, matching the prototype's two heights.
struct SalesChart: View {
    let days: [DailySale]
    var height: CGFloat = 110

    var body: some View {
        if days.isEmpty {
            Text("No paid sales in this period.")
                .font(.system(size: 11))
                .foregroundStyle(ChmabaColor.faint)
                .padding(.top, 10)
        } else {
            let peak = max(days.map(\.value).max() ?? 1, 0.0001)
            HStack(alignment: .bottom, spacing: 5) {
                ForEach(Array(days.enumerated()), id: \.offset) { index, day in
                    UnevenRoundedRectangle(
                        topLeadingRadius: 5, topTrailingRadius: 5, style: .continuous
                    )
                    .fill(index == days.count - 1 ? ChmabaColor.purple : Color(hex: 0xDCD9FB))
                    .frame(height: max(4, height * (day.value / peak)))
                    .frame(maxWidth: .infinity)
                }
            }
            .frame(height: height, alignment: .bottom)
        }
    }
}
