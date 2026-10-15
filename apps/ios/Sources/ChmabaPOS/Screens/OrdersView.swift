import SwiftUI

/// Orders, ported from `data-screen="orders"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /orders?limit=50`.
///
/// This is a bottom-nav tab rather than a More destination, so it is reachable
/// without opening the menu.
struct OrdersView: View {
    @EnvironmentObject private var session: Session

    var onOpenOrder: (Order) -> Void

    enum Filter: String, CaseIterable, Hashable {
        case all = "All orders"
        case paid = "Paid"
        case pending = "Pending"
        case pickup = "Pickup"
        case cancelled = "Cancelled"

        func matches(_ order: Order) -> Bool {
            switch self {
            case .all: return true
            case .paid: return order.displayStatus == "Paid"
            case .pending: return order.displayStatus == "Pending"
            case .pickup: return order.displayStatus == "Pickup"
            case .cancelled: return order.displayStatus == "Cancelled"
            }
        }
    }

    @State private var orders: [Order] = []
    @State private var loading = true
    @State private var error: String?
    @State private var filter: Filter = .all

    private var storeName: String { session.workspaceName ?? "Your store" }
    private var visible: [Order] { orders.filter { filter.matches($0) } }
    private func count(_ filter: Filter) -> Int { orders.filter { filter.matches($0) }.count }

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
                    Text("Orders")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Every order from \(storeName).")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer()
                IconButton(symbol: "arrow.clockwise") { Task { await load() } }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        StatGrid(columns: 3) {
            StatTile(label: "Loaded", value: "\(orders.count)", tone: .violet, compact: true)
            StatTile(label: "Paid", value: "\(count(.paid))", tone: .green, compact: true)
            StatTile(label: "Pending", value: "\(count(.pending))", tone: .yellow, compact: true)
        }

        if loading {
            noticeLine("Loading orders…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if orders.isEmpty {
            noticeLine("No orders yet.")
        } else {
            ChipRow(items: Filter.allCases, title: \.rawValue, selection: $filter, segmented: false)
                .padding(.top, 12)
                .padding(.bottom, 12)

            PanelList {
                let rows = visible
                if rows.isEmpty {
                    noticeLine("No orders match this filter.").padding(16)
                } else {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, order in
                        ListRow(showsDivider: index < rows.count - 1) {
                            AnyView(
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(order.orderNumber)
                                        .font(.system(size: 12, weight: .heavy))
                                        .foregroundStyle(ChmabaColor.textPrimary)
                                        .lineLimit(1)
                                    Text("\(order.customerName ?? "Walk-in") · \(order.timeLabel)")
                                        .font(.system(size: 10))
                                        .foregroundStyle(ChmabaColor.faint)
                                        .lineLimit(1)
                                }
                            )
                        } trailing: {
                            HStack(spacing: 8) {
                                ChmabaBadge(text: order.methodLabel, tone: order.tenderTone)
                                ChmabaBadge(text: order.displayStatus, tone: order.badgeTone, showDot: true)
                                Text(money(order.total.value, code: order.currencyCode))
                                    .font(.system(size: 12, weight: .heavy))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                            }
                        } action: {
                            onOpenOrder(order)
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
            orders = try await APIClient.shared.get("orders?limit=50", as: [Order].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load orders."
            loading = false
        }
    }
}
