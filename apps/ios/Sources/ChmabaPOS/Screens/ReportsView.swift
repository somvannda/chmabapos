import SwiftUI

/// Reports, ported from `data-screen="reports"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /reports/summary`.
///
/// The prototype's header shows a date-range chip ("Oct 1 – Oct 8") and a "Compare"
/// chip. Neither has an API behind it, and the Android client replaced them with the
/// five `ReportPeriod` windows. Same here -- a control that cannot do anything is
/// worse than one that does less.
struct ReportsView: View {
    @EnvironmentObject private var session: Session

    let onBack: () -> Void

    @State private var summary: ReportSummary?
    @State private var loading = true
    @State private var error: String?
    @State private var period: ReportPeriod = .today

    private var currency: String { summary?.currency ?? session.currencyCode }

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 2) { content }
        }
        .background(ChmabaColor.background)
        .task { await load() }
    }

    private var appBar: some View {
        AppBar {
            HStack(spacing: 10) {
                IconButton(symbol: "chevron.left", action: onBack)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Reports")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text(periodSubtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer()
                IconButton(symbol: "arrow.down.to.line") {
                    // TODO: export, once the CSV endpoint is wired.
                }
            }
        }
    }

    private var periodSubtitle: String {
        guard let summary, let from = summary.fromDate else {
            return "Sales for the selected period."
        }
        return summary.toDate.map { "\(from) – \($0)" } ?? "Since \(from)"
    }

    @ViewBuilder
    private var content: some View {
        ChipRow(items: ReportPeriod.allCases, title: \.label, selection: $period, segmented: true)
            .padding(.bottom, 12)
            .onChange(of: period) { _, _ in Task { await load() } }

        if loading {
            noticeLine("Loading the report…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if let summary {
            StatGrid(columns: 2) {
                StatTile(
                    label: "Gross sales",
                    value: money(decimal(summary.grossSales), code: currency),
                    detail: "Before discounts",
                    tone: .violet, compact: true
                )
                StatTile(
                    label: "Net sales",
                    value: money(summary.effectiveNet, code: currency),
                    detail: "After discounts & refunds",
                    tone: .green, compact: true
                )
                StatTile(
                    label: "Transactions",
                    value: "\(summary.transactions)",
                    detail: String(format: "%.1f avg. per day", summary.averagePerDay),
                    tone: .red, compact: true
                )
                StatTile(
                    label: "Refunds",
                    value: money(decimal(summary.refunds), code: currency),
                    detail: summary.refundsCount == 1 ? "1 order" : "\(summary.refundsCount) orders",
                    tone: .yellow, compact: true
                )
            }

            salesByDay(summary)
            breakdown("Payment breakdown", rows: summary.paymentMethods, empty: "No payments recorded in this period.")
            breakdown("Top categories", rows: summary.categorySales, empty: "No category sales in this period.")
        }
    }

    private func salesByDay(_ summary: ReportSummary) -> some View {
        POSPanel {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Sales by day")
                        .font(.system(size: 13, weight: .heavy))
                        .tracking(-0.025)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("\(summary.dailySales.count) day\(summary.dailySales.count == 1 ? "" : "s")")
                        .font(.system(size: 11))
                        .foregroundStyle(Color(hex: 0x999AA4))
                }
                Spacer()
                ChmabaBadge(text: "\(summary.dailySales.count) days", tone: .green)
            }

            if summary.dailySales.isEmpty {
                noticeLine("No paid sales in this period.")
            } else {
                SalesChart(days: summary.dailySales, height: 130)
                    .padding(.top, 14)
            }
        }
        .padding(.top, 12)
    }

    private func breakdown(_ title: String, rows: [MixRow], empty: String) -> some View {
        let mix = salesMix(rows)
        return POSPanel {
            SectionHeading(title: title)

            if mix.isEmpty {
                noticeLine(empty)
            } else {
                VStack(spacing: 10) {
                    ForEach(Array(mix.enumerated()), id: \.element.id) { index, share in
                        HStack(spacing: 9) {
                            Circle()
                                .fill(shareColour(index))
                                .frame(width: 6, height: 6)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(share.label)
                                    .font(.system(size: 11, weight: .bold))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                    .lineLimit(1)
                                ProgressTrack(fraction: Double(share.percent) / 100)
                            }
                            Text("\(share.percent)%")
                                .font(.system(size: 12, weight: .heavy))
                                .foregroundStyle(ChmabaColor.textPrimary)
                                .frame(width: 38, alignment: .trailing)
                        }
                    }
                }
                .padding(.top, 12)
            }
        }
        .padding(.top, 12)
    }

    /// The prototype's own cycle: purple, lime, peach, lavender-violet, grey.
    private func shareColour(_ index: Int) -> Color {
        [ChmabaColor.purple, ChmabaColor.lime, ChmabaColor.peach,
         Color(hex: 0xB9B2FA), ChmabaColor.grey400][index % 5]
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    private func decimal(_ raw: String?) -> Decimal { Decimal(string: raw ?? "0") ?? 0 }

    private func load() async {
        if summary == nil { loading = true }
        error = nil

        var path = "reports/summary?from_date=\(period.from)"
        if let to = period.to { path += "&to_date=\(to)" }

        do {
            summary = try await APIClient.shared.get(path, as: ReportSummary.self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load the report."
            loading = false
        }
    }
}
