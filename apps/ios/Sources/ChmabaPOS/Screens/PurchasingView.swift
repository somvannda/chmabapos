import SwiftUI

/// Purchasing, ported from `data-screen="purchasing"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /purchases`.
///
/// Two deviations from the prototype, both because the payload does not support it:
///
///   - The prototype's filter chips are Open / Partial / Received. The Android client
///     uses five (All, Open, Partial, Received, Draft) so a draft is reachable; same
///     here.
///   - The prototype shows a "Reorder suggestions" card. Nothing supplies it -- the
///     Android client keeps the card hidden until an endpoint exists. Same here: it is
///     omitted rather than filled with invented rows.
struct PurchasingView: View {
    @EnvironmentObject private var session: Session

    let onBack: () -> Void

    enum StatusFilter: String, CaseIterable, Hashable {
        case all = "All"
        case open = "Open"
        case partial = "Partial"
        case received = "Received"
        case draft = "Draft"

        func matches(_ status: String) -> Bool {
            switch self {
            case .all: return true
            case .open: return status.lowercased() == "open" || status.lowercased() == "ordered"
            case .partial: return status.lowercased() == "partial"
            case .received: return status.lowercased() == "received"
            case .draft: return status.lowercased() == "draft"
            }
        }
    }

    @State private var orders: [PurchaseOrder] = []
    @State private var loading = true
    @State private var error: String?
    @State private var filter: StatusFilter = .all

    private var visible: [PurchaseOrder] {
        orders.filter { filter.matches($0.status) }
    }

    private func count(_ filter: StatusFilter) -> Int {
        orders.filter { filter.matches($0.status) }.count
    }

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
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Purchasing")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Purchase orders and receiving.")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer()
                ChmabaButton(text: "New PO", variant: .primary, size: .small, leadingIcon: .plus) {
                    // TODO: create-PO flow (POST /purchases), which needs a supplier
                    // and at least one line plus a variant where the product has them.
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        StatGrid(columns: 3) {
            StatTile(label: "Open", value: "\(count(.open))", tone: .yellow, compact: true)
            StatTile(label: "Received", value: "\(count(.received))", tone: .green, compact: true)
            StatTile(label: "Draft", value: "\(count(.draft))", tone: .violet, compact: true)
        }

        if loading {
            noticeLine("Loading purchase orders…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if orders.isEmpty {
            noticeLine("No purchase orders yet.")
        } else {
            ChipRow(items: StatusFilter.allCases, title: \.rawValue, selection: $filter, segmented: false)
                .padding(.top, 12)
                .padding(.bottom, 12)

            PanelList {
                let rows = visible
                if rows.isEmpty {
                    noticeLine("No purchase orders in this view.").padding(16)
                } else {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, order in
                        ListRow(showsDivider: index < rows.count - 1) {
                            AnyView(
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(order.poNumber)
                                        .font(.system(size: 12, weight: .heavy))
                                        .foregroundStyle(ChmabaColor.textPrimary)
                                        .lineLimit(1)
                                    Text("\(order.supplier ?? "No supplier") · \(order.lineCount) line\(order.lineCount == 1 ? "" : "s") · \(order.dateLabel)")
                                        .font(.system(size: 10))
                                        .foregroundStyle(ChmabaColor.faint)
                                        .lineLimit(1)
                                }
                            )
                        } trailing: {
                            VStack(alignment: .trailing, spacing: 4) {
                                // Derivable here, unlike the Android client which shows
                                // "—": each line carries a unit cost.
                                if let total = order.computedTotal {
                                    Text(money(total, code: session.currencyCode))
                                        .font(.system(size: 12, weight: .heavy))
                                        .foregroundStyle(ChmabaColor.textPrimary)
                                } else {
                                    Text("—")
                                        .font(.system(size: 12, weight: .heavy))
                                        .foregroundStyle(ChmabaColor.faint)
                                }
                                ChmabaBadge(text: order.displayStatus, tone: order.badgeTone)
                            }
                        } action: {
                            // TODO: PO detail, once it exists.
                        }
                    }
                }
            }
        }
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    private func load() async {
        if orders.isEmpty { loading = true }
        error = nil
        do {
            orders = try await APIClient.shared.get("purchases?limit=50", as: [PurchaseOrder].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load purchases."
            loading = false
        }
    }
}
