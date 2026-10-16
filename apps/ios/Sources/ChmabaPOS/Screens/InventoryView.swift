import SwiftUI

/// Inventory, ported from `data-screen="inventory"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /inventory`.
///
/// Stock value sums `on_hand × cost_price` over rows that HAVE a cost basis. Rows
/// without one are excluded and counted, rather than treated as zero -- the API
/// documents that missing cost must not be read as free stock, and the Android client
/// shows the same disclosure.
struct InventoryView: View {
    @EnvironmentObject private var session: Session

    let onBack: () -> Void

    enum StockFilter: String, CaseIterable, Hashable {
        case all = "All stock"
        case low = "Low stock"
        case healthy = "Healthy"
    }

    @State private var items: [InventoryItem] = []
    @State private var loading = true
    @State private var error: String?
    @State private var filter: StockFilter = .all
    /// The item whose count is being adjusted.
    @State private var adjustTarget: InventoryItem?

    private var visible: [InventoryItem] {
        switch filter {
        case .all: return items
        case .low: return items.filter { $0.status != .healthy }
        case .healthy: return items.filter { $0.status == .healthy }
        }
    }

    private var pricedItems: [InventoryItem] { items.filter { $0.stockValue != nil } }
    private var unpricedCount: Int { items.count - pricedItems.count }

    private var totalValue: Decimal {
        pricedItems.reduce(Decimal.zero) { $0 + ($1.stockValue ?? 0) }
    }

    private var totalUnits: Double {
        items.reduce(0) { $0 + $1.onHand }
    }

    private var attentionCount: Int {
        items.filter { $0.status != .healthy }.count
    }

    private var serialTracked: [InventoryItem] {
        items.filter(\.trackSerials)
    }

    var body: some View {
        Group {
            if let adjustTarget {
                StockAdjustView(item: adjustTarget) {
                    self.adjustTarget = nil
                    Task { await load() }
                } onBack: {
                    self.adjustTarget = nil
                }
            } else {
                VStack(spacing: 0) {
                    appBar
                    PageBody(topPadding: 2) { content }
                }
            }
        }
        .background(ChmabaColor.background)
        .task { await load() }
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Inventory")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Keep your shelves ready for the next rush.")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer()
                IconButton(icon: .download) {
                    // TODO: CSV export + share sheet.
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        StatGrid(columns: 3) {
            StatTile(
                label: "Value",
                value: money(totalValue, code: session.currencyCode),
                tone: .violet, compact: true
            )
            StatTile(label: "Units", value: "\(Int(totalUnits))", tone: .green, compact: true)
            StatTile(label: "Attention", value: "\(attentionCount)", tone: .yellow, compact: true)
        }

        if unpricedCount > 0 {
            Text(unpricedCount == 1
                 ? "1 product has no cost recorded, so it is left out of the value."
                 : "\(unpricedCount) products have no cost recorded, so they are left out of the value.")
                .font(.system(size: 10))
                .foregroundStyle(ChmabaColor.faint)
                .padding(.top, 8)
        }

        if loading {
            noticeLine("Loading inventory…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if items.isEmpty {
            noticeLine("Nothing in stock yet.")
        } else {
            ChipRow(items: StockFilter.allCases, title: \.rawValue, selection: $filter, segmented: false)
                .padding(.top, 12)
                .padding(.bottom, 12)

            PanelList {
                let rows = visible
                if rows.isEmpty {
                    noticeLine("Nothing in this view.").padding(16)
                } else {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, item in
                        ListRow(showsDivider: index < rows.count - 1) {
                            AnyView(
                                HStack(spacing: 11) {
                                    MarkChip(text: initials(item.productName), background: tint(item))
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.productName)
                                            .font(.system(size: 12, weight: .bold))
                                            .foregroundStyle(ChmabaColor.textPrimary)
                                            .lineLimit(1)
                                        Text("\(item.sku) · reorder at \(item.reorderPoint)")
                                            .font(.system(size: 10))
                                            .foregroundStyle(ChmabaColor.faint)
                                            .lineLimit(1)
                                    }
                                }
                            )
                        } trailing: {
                            ChmabaBadge(text: "\(Int(item.onHand)) units", tone: item.badgeTone)
                        } action: {
                            adjustTarget = item
                        }
                    }
                }
            }

            HStack(spacing: 12) {
                ChmabaButton(text: "Adjust stock", variant: .outline, size: .medium, fullWidth: true) {
                    adjustTarget = visible.first
                }
                ChmabaButton(text: "Receive stock", variant: .primary, size: .medium, fullWidth: true) {
                    // The Android client routes this to its not-yet notice; so do we.
                }
            }
            .padding(.top, 12)

            if !serialTracked.isEmpty {
                POSPanel {
                    SectionHeading(
                        title: "Serials",
                        subtitle: "Units are tracked one by one by serial / IMEI."
                    )
                    VStack(spacing: 10) {
                        ForEach(serialTracked.prefix(3), id: \.id) { item in
                            HStack {
                                Text(item.productName)
                                    .font(.system(size: 12, weight: .bold))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                    .lineLimit(1)
                                Spacer()
                                ChmabaBadge(text: "\(Int(item.onHand)) in stock", tone: .blue)
                            }
                        }
                    }
                    .padding(.top, 4)
                }
                .padding(.top, 12)
            }
        }
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    private func initials(_ name: String) -> String {
        name.split(separator: " ").prefix(2).compactMap { $0.first.map(String.init) }.joined().uppercased()
    }

    private func tint(_ item: InventoryItem) -> Color {
        let palette = [Color(hex: 0xD7C0A2), Color(hex: 0xB9D7A2), Color(hex: 0xF0C986), Color(hex: 0xC99E83)]
        return palette[abs(item.productName.hashValue) % palette.count]
    }

    private func load() async {
        if items.isEmpty { loading = true }
        error = nil
        do {
            items = try await APIClient.shared.get("inventory", as: [InventoryItem].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load inventory."
            loading = false
        }
    }
}
