import SwiftUI

/// One order, with its lines and how it was paid. Ported from the prototype's
/// `data-screen="order-detail"`.
///
/// Reads `GET /orders/{id}` -> `OrderRead`, which carries `items`, `tenders` and `payments`.
///
/// Read-only. The prototype puts "Print receipt", "Refund" and "Cancel order" along the
/// bottom, and none of the three is available here: the iOS app has no receipt printer, and
/// refund and cancel are writes that belong to a deliberate, confirmed action rather than a
/// button on a read-only view. A control that only reported its own absence would be worse
/// than no control, so the screen shows what happened and stops.
struct OrderDetailView: View {
    let order: Order
    let onBack: () -> Void

    @EnvironmentObject private var session: Session

    @State private var detail: Order?
    @State private var loading = true
    @State private var error: String?

    private var shown: Order { detail ?? order }

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
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("#\(shown.orderNumber)")
                        .font(.system(size: 18, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text(Self.subtitle(shown))
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                ChmabaBadge(
                    text: shown.status.capitalized,
                    tone: shown.status == "paid" ? .green : .yellow
                )
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        if loading {
            noticeLine("Loading order…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else {
            itemsCard
            paymentCard

            if let balance = balanceDue, balance > 0 {
                Text("\(money(balance, code: shown.currencyCode)) is still owed on this order.")
                    .font(.system(size: 10.5))
                    .foregroundStyle(BadgeTone.yellow.foreground)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 12)
            }
        }
    }

    private var itemsCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Items")
                .font(.system(size: 12.5, weight: .heavy))
                .foregroundStyle(ChmabaColor.textPrimary)

            if shown.items.isEmpty {
                Text("This order's lines are not available.")
                    .font(.system(size: 10.5))
                    .foregroundStyle(ChmabaColor.faint)
                    .padding(.top, 10)
            } else {
                VStack(spacing: 10) {
                    ForEach(shown.items) { item in
                        HStack(alignment: .top, spacing: 10) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(item.productName) × \(Self.quantity(item.quantity))")
                                    .font(.system(size: 12, weight: .bold))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                if !item.optionSummary.isEmpty {
                                    Text(item.optionSummary)
                                        .font(.system(size: 10))
                                        .foregroundStyle(ChmabaColor.faint)
                                }
                            }
                            Spacer(minLength: 0)
                            Text(money(item.lineTotal.value, code: shown.currencyCode))
                                .font(.system(size: 12, weight: .bold))
                                .foregroundStyle(ChmabaColor.textPrimary)
                        }
                    }
                }
                .padding(.top, 10)
            }

            VStack(spacing: 6) {
                totalRow("Subtotal", money(shown.subtotal.value, code: shown.currencyCode))
                if shown.discount.value > 0 {
                    totalRow(
                        "Discount",
                        "−" + money(shown.discount.value, code: shown.currencyCode),
                        tint: BadgeTone.red.foreground
                    )
                }
                totalRow("Tax", money(shown.tax.value, code: shown.currencyCode))
                Divider().padding(.top, 4)
                totalRow("Total", money(shown.total.value, code: shown.currencyCode), bold: true)
            }
            .padding(.top, 12)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 16))
    }

    private var paymentCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Payment")
                .font(.system(size: 12.5, weight: .heavy))
                .foregroundStyle(ChmabaColor.textPrimary)

            ForEach(Array(shown.tenders.enumerated()), id: \.offset) { _, tender in
                HStack(spacing: 8) {
                    // A change tender sits in the same list as the payment, so it is labelled
                    // rather than mistaken for a second method.
                    ChmabaBadge(
                        text: tender.kind == "change"
                            ? "Change"
                            : tender.method.uppercased(),
                        tone: tender.kind == "change" ? .neutral : shown.tenderTone
                    )
                    Spacer(minLength: 0)
                    Text(money(tender.amount.value, code: shown.currencyCode))
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(ChmabaColor.textPrimary)
                }
                .padding(.top, 10)
            }

            Text(Self.paidLine(shown))
                .font(.system(size: 10.5))
                .foregroundStyle(ChmabaColor.faint)
                .padding(.top, 10)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 16))
        .padding(.top, 12)
    }

    private var balanceDue: Decimal? {
        guard shown.total.value > shown.amountPaid.value else { return nil }
        return shown.total.value - shown.amountPaid.value
    }

    private func totalRow(_ label: String, _ value: String,
                          tint: Color = ChmabaColor.muted, bold: Bool = false) -> some View {
        HStack {
            Spacer(minLength: 0)
            Text(label)
                .font(.system(size: bold ? 12.5 : 12, weight: bold ? .heavy : .regular))
                .foregroundStyle(ChmabaColor.muted)
            Spacer(minLength: 0)
            Text(value)
                .font(.system(size: bold ? 12.5 : 12, weight: bold ? .heavy : .bold))
                .foregroundStyle(tint == ChmabaColor.muted ? ChmabaColor.textPrimary : tint)
        }
    }

    private func noticeLine(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(ChmabaColor.faint)
            .padding(.top, 10)
    }

    // MARK: Formatting

    /// "Walk-in · 8 Oct, 10:42 AM" — the customer where the API named one.
    static func subtitle(_ order: Order) -> String {
        let who = order.customerName?.isEmpty == false ? order.customerName! : "Walk-in"
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = Calendar.current.isDateInToday(order.createdAt)
            ? "h:mm a"
            : "d MMM, h:mm a"
        return "\(who) · \(formatter.string(from: order.createdAt))"
    }

    static func paidLine(_ order: Order) -> String {
        switch order.status {
        case "paid": return "Paid in full."
        case "refunded": return "Refunded."
        default: return "Status: \(order.status)."
        }
    }

    /// Whole units print without a decimal point; a weighed line keeps its fraction.
    static func quantity(_ value: Double) -> String {
        value == value.rounded() ? String(Int(value)) : String(format: "%.3f", value)
    }

    private func load() async {
        if detail == nil { loading = true }
        error = nil
        do {
            detail = try await APIClient.shared.get("orders/\(order.id.uuidString)", as: Order.self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load this order."
            loading = false
        }
    }
}
