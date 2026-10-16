import SwiftUI

/// A customer, with what they have bought. Ported from the prototype's
/// `data-screen="customer-detail"`, following the Android client where the two disagree.
///
/// Reads `GET /customers/{id}` -> `CustomerDetailRead`, which nests the FULL `OrderRead`
/// list rather than a summary.
///
/// Deliberately read-only for loyalty. The prototype shows a stepper and an "Add points"
/// button, but the Android client removed them and says why: *"Points are earned on paid
/// orders, so they are not set here."* Points are a consequence of a sale, not a field to
/// type into, and a control that adjusts them silently would make the number untrustworthy.
/// `PATCH /customers/{id}/points` does exist, so this is a product decision rather than a
/// missing endpoint.
struct CustomerDetailView: View {
    @EnvironmentObject private var session: Session

    let customer: Customer
    let onBack: () -> Void

    @State private var detail: CustomerDetail?
    @State private var loading = true
    @State private var error: String?

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 2) { content }
        }
        .background(ChmabaColor.background)
        .task { await load() }
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            VStack(alignment: .leading, spacing: 2) {
                Text(customer.name)
                    .font(.system(size: 18, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                    .lineLimit(1)
                Text("Customer since \(Self.since(customer.createdAt))")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        if loading {
            noticeLine("Loading customer…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else {
            StatGrid(columns: 3) {
                StatTile(
                    label: "Orders",
                    value: "\(detail?.ordersCount ?? 0)",
                    tone: .violet,
                    compact: true
                )
                StatTile(
                    label: "Spent",
                    value: money(detail?.totalSpent.value ?? 0, code: session.currencyCode),
                    tone: .green,
                    compact: true
                )
                StatTile(
                    label: "Points",
                    value: "\(Int(truncating: customer.points.value as NSDecimalNumber))",
                    tone: .yellow,
                    compact: true
                )
            }
            .padding(.bottom, 14)

            contactCard
            loyaltyCard

            let orders = detail?.orders ?? []
            Text("Recent orders")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 16)
                .padding(.bottom, 8)

            if orders.isEmpty {
                noticeLine("No orders yet.")
            } else {
                PanelList {
                    ForEach(Array(orders.prefix(20).enumerated()), id: \.element.id) { index, order in
                        ListRow(showsDivider: index < min(orders.count, 20) - 1) {
                            AnyView(
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("#\(order.orderNumber)")
                                        .font(.system(size: 12, weight: .bold))
                                        .foregroundStyle(ChmabaColor.textPrimary)
                                    Text(Self.stamp(order.createdAt))
                                        .font(.system(size: 10))
                                        .foregroundStyle(ChmabaColor.faint)
                                }
                            )
                        } trailing: {
                            VStack(alignment: .trailing, spacing: 4) {
                                Text(money(order.total.value, code: order.currencyCode))
                                    .font(.system(size: 12, weight: .heavy))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                ChmabaBadge(
                                    text: order.status.capitalized,
                                    tone: order.status == "paid" ? .green : .neutral
                                )
                            }
                        } action: {
                            // Nothing to open: order detail is not built on iOS yet.
                        }
                    }
                }
            }
        }
    }

    private var contactCard: some View {
        PanelList {
            ListRow(showsDivider: false) {
                AnyView(
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Contact")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(ChmabaColor.textPrimary)
                        Text(customer.contact)
                            .font(.system(size: 10.5))
                            .foregroundStyle(ChmabaColor.faint)
                    }
                )
            } trailing: {
                if !customer.isActive {
                    ChmabaBadge(text: "Inactive", tone: .neutral)
                }
            } action: {
                // Read-only: customers are edited in the web app.
            }
        }
    }

    private var loyaltyCard: some View {
        PanelList {
            ListRow(showsDivider: false) {
                AnyView(
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Loyalty points")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(ChmabaColor.textPrimary)
                        Text("Points are earned on paid orders, so they are not set here.")
                            .font(.system(size: 10.5))
                            .lineSpacing(2)
                            .foregroundStyle(ChmabaColor.faint)
                    }
                )
            } trailing: {
                ChmabaBadge(
                    text: "\(Int(truncating: customer.points.value as NSDecimalNumber)) pts",
                    tone: .violet
                )
            } action: {}
        }
        .padding(.top, 14)
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    // MARK: Formatting

    static func since(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "d MMM yyyy"
        return formatter.string(from: date)
    }

    static func stamp(_ date: Date) -> String {
        let calendar = Calendar.current
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        if calendar.isDateInToday(date) {
            formatter.dateFormat = "h:mm a"
        } else {
            formatter.dateFormat = "d MMM"
        }
        return formatter.string(from: date)
    }

    private func load() async {
        if detail == nil { loading = true }
        error = nil
        do {
            detail = try await APIClient.shared.get(
                "customers/\(customer.id.uuidString)", as: CustomerDetail.self
            )
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load this customer."
            loading = false
        }
    }
}
