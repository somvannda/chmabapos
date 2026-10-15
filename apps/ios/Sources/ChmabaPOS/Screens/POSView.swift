import SwiftUI

/// The selling surface: product grid, search, and a cart.
///
/// Mirrors the Android client's mobile layout — `POSScreen.kt` puts the cart in a
/// bottom bar and a sheet rather than the web's fixed 320pt sidebar. Same
/// information architecture, idiomatically expressed for iOS.
@MainActor
final class POSViewModel: ObservableObject {
    enum LoadState: Equatable {
        case loading
        case ready([ProductRead])
        case failed(String)
    }

    @Published private(set) var state: LoadState = .loading
    @Published var search = ""
    /// The prototype's first chip is "All items", then the distinct categories.
    @Published var category: String = "All items"

    static let allItems = "All items"

    var categories: [String] {
        guard case let .ready(products) = state else { return [Self.allItems] }
        let names = products.compactMap { $0.category?.name }
        return [Self.allItems] + Array(Set(names)).sorted()
    }
    @Published private(set) var cart: [CartLine] = []

    private let api = APIClient.shared

    struct CartLine: Identifiable, Equatable {
        let product: ProductRead
        var quantity: Int
        var id: UUID { product.id }
        var lineTotal: Decimal { product.price.value * Decimal(quantity) }
    }

    func load() async {
        state = .loading
        do {
            let products: [ProductRead] = try await api.get("products", as: [ProductRead].self)
            state = .ready(products)
        } catch let error as APIError {
            state = .failed(error.errorDescription ?? "Could not load products.")
        } catch {
            state = .failed("Could not load products.")
        }
    }

    var visibleProducts: [ProductRead] {
        guard case let .ready(products) = state else { return [] }
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return products.filter { product in
            let matchesCategory = category == Self.allItems
                || (product.category?.name ?? "") == category
            guard matchesCategory else { return false }
            guard !query.isEmpty else { return true }
            return product.name.lowercased().contains(query)
                || product.sku.lowercased().contains(query)
                || (product.barcode?.lowercased().contains(query) ?? false)
        }
    }

    var itemCount: Int { cart.reduce(0) { $0 + $1.quantity } }
    var subtotal: Decimal { cart.reduce(Decimal.zero) { $0 + $1.lineTotal } }

    // MARK: Discount
    //
    // The Android client supports None / Percent / Amount, and coerces the discount
    // into 0...subtotal so a fat-fingered value cannot make the total negative.

    enum DiscountMode: String, CaseIterable, Hashable {
        case none = "None"
        case percent = "Percent"
        case amount = "Amount"
    }

    @Published var discountMode: DiscountMode = .none
    @Published var discountValue: Decimal = 0

    /// The discount actually applied, clamped to the subtotal.
    var discount: Decimal {
        switch discountMode {
        case .none: return 0
        case .percent:
            let raw = subtotal * (discountValue / 100)
            return min(max(raw, 0), subtotal)
        case .amount:
            return min(max(discountValue, 0), subtotal)
        }
    }

    private var taxable: Decimal { subtotal - discount }

    /// 10% tax, matching the Android client's `TAX_RATE = 0.10`.
    /// TODO: read this from store settings once the API exposes it; a hard-coded rate
    /// is fine for a dev slice and wrong for a real till.
    var tax: Decimal { taxable * Decimal(0.10) }

    var total: Decimal { taxable + tax }

    // MARK: Submission

    @Published private(set) var submitting = false
    @Published private(set) var completed: Order?
    @Published var saleError: String?

    /// Posts the sale.
    ///
    /// `tendered` is what the customer handed over (cash) or the exact amount due
    /// (KHQR). Change is computed server-side and comes back as a change tender.
    func submit(method: String, tendered: Decimal) async {
        guard !cart.isEmpty, !submitting else { return }
        submitting = true
        saleError = nil

        let request = OrderCreateRequest(
            items: cart.map {
                OrderItemCreate(productId: $0.product.id.uuidString, quantity: $0.quantity)
            },
            // The method travels on the tender. Sending `payment_method` as well is a
            // 400 ("Use tenders or payment_method, not both"), so it is not sent.
            tenders: [
                OrderTenderCreate(
                    method: method,
                    currencyCode: currencyCode,
                    amount: "\(tendered)"
                )
            ],
            discount: "\(discount)",
            clientOrderId: UUID().uuidString,
            orderType: "takeaway",
            customerName: attachedCustomer,
            changeCurrencyCode: method == "cash" ? currencyCode : nil
        )

        do {
            let order: Order = try await api.post("orders", body: request, as: Order.self)
            completed = order
            cart.removeAll()
            discountMode = .none
            discountValue = 0
            attachedCustomer = nil
            submitting = false
        } catch let apiError as APIError {
            saleError = apiError.errorDescription
            submitting = false
        } catch {
            saleError = "The sale was not recorded."
            submitting = false
        }
    }

    func dismissCompleted() { completed = nil }

    /// Currency for tenders and money formatting. Set from the workspace on sign-in.
    var currencyCode: String = "USD"

    /// Customer name to record against the sale, when one is attached.
    @Published var attachedCustomer: String?

    func clearCart() {
        cart.removeAll()
        discountMode = .none
        discountValue = 0
        attachedCustomer = nil
    }

    func add(_ product: ProductRead) {
        if let index = cart.firstIndex(where: { $0.id == product.id }) {
            let cap = product.trackInventory ? Int(product.onHand) : nil
            if cap.map({ cart[index].quantity < $0 }) ?? true {
                cart[index].quantity += 1
            }
        } else {
            cart.append(CartLine(product: product, quantity: 1))
        }
    }

    func setQuantity(_ quantity: Int, for line: CartLine) {
        guard let index = cart.firstIndex(where: { $0.id == line.id }) else { return }
        if quantity <= 0 {
            cart.remove(at: index)
        } else {
            let cap = line.product.trackInventory ? Int(line.product.onHand) : nil
            cart[index].quantity = cap.map { min(quantity, $0) } ?? quantity
        }
    }
}

struct POSView: View {
    @EnvironmentObject private var session: Session
    @StateObject private var model = POSViewModel()
    @State private var cartOpen = false
    @State private var scanOpen = false
    @State private var notice: String?

    /// `.pgrid` — two columns with a 9pt gap on mobile, not the adaptive 140pt grid the
    /// web uses.
    private let columns = [
        GridItem(.flexible(), spacing: 9),
        GridItem(.flexible(), spacing: 9),
    ]

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            VStack(spacing: 0) {
                if let notice {
                    ShellNotice(message: notice) { self.notice = nil }
                }
                topBar
                content
            }

            cartFab
        }
        .background(ChmabaColor.background)
        .task {
            model.currencyCode = session.currencyCode
            if case .loading = model.state { await model.load() }
        }
        .sheet(isPresented: $cartOpen) { CartSheet(model: model) }
        .sheet(isPresented: $scanOpen) {
            ScanSheet { code in
                model.search = code
            }
        }
    }

    /// `.fab` — 54x54, radius 18, purple, 16pt from the right and 96pt from the bottom,
    /// with the prototype's purple glow.
    ///
    /// The prototype's FAB carries no count. This adds one, because a till needs to see
    /// at a glance that something is in the cart, and the Android client's cart bar
    /// shows the same figure. It is the one deliberate addition here.
    private var cartFab: some View {
        Button {
            cartOpen = true
        } label: {
            ZStack {
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(ChmabaColor.purple)
                    .frame(width: 54, height: 54)
                    .shadow(color: ChmabaColor.purple.opacity(0.42), radius: 14, y: 6)
                Image(systemName: "cart")
                    .font(.system(size: 20))
                    .foregroundStyle(.white)
            }
            .overlay(alignment: .topTrailing) {
                if model.itemCount > 0 {
                    Text("\(model.itemCount)")
                        .font(.system(size: 10, weight: .heavy))
                        .foregroundStyle(ChmabaColor.inkStrong)
                        .frame(minWidth: 18, minHeight: 18)
                        .background(ChmabaColor.lime, in: Circle())
                        .offset(x: 5, y: -5)
                }
            }
        }
        .buttonStyle(ChmabaPressStyle(scale: 0.94))
        .padding(.trailing, 16)
        .padding(.bottom, 96)
        .accessibilityLabel(model.itemCount == 0
            ? "Cart, empty"
            : "Cart, \(model.itemCount) item\(model.itemCount == 1 ? "" : "s")")
    }

    // MARK: Top bar

    /// Mirrors the prototype's POS app bar: "Register 01 is ready" over "Make a sale",
    /// with small outline Scan and soft Hold buttons; then the search row with a purple
    /// camera glyph; then the category chips.
    private var topBar: some View {
        VStack(spacing: 0) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Circle().fill(BadgeTone.green.dot).frame(width: 6, height: 6)
                        Text("Register 01 is ready")
                            .font(.system(size: 11))
                            .foregroundStyle(ChmabaColor.muted)
                    }
                    Text("Make a sale")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                }

                Spacer(minLength: 0)

                HStack(spacing: 7) {
                    ChmabaButton(text: "Scan", variant: .outline, size: .small) {
                        scanOpen = true
                    }
                    ChmabaButton(text: "Hold", variant: .soft, size: .small) {
                        notice = "Holding an order isn't in the iOS app yet. Use the web POS for it."
                    }
                }
            }

            // .search — height 44, radius 12, border, purple camera at the trailing edge.
            HStack(spacing: 9) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 15))
                    .foregroundStyle(ChmabaColor.ghost)

                TextField("Search or scan name, SKU, barcode…", text: $model.search)
                    .font(.system(size: 13))
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.search)

                Button {
                    scanOpen = true
                } label: {
                    Image(systemName: "camera")
                        .font(.system(size: 15))
                        .foregroundStyle(ChmabaColor.purple)
                }
                .buttonStyle(ChmabaPressStyle())
                .accessibilityLabel("Scan a barcode")
            }
            .padding(.horizontal, 13)
            .frame(height: 44)
            .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
            .overlay {
                RoundedRectangle(cornerRadius: 12).strokeBorder(ChmabaColor.outline, lineWidth: 1)
            }
            .padding(.top, 12)

            if model.categories.count > 1 {
                ChipRow(
                    items: model.categories,
                    title: { $0 },
                    selection: $model.category,
                    segmented: false
                )
                .padding(.top, 12)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 12)
        .padding(.bottom, 10)
        .background(ChmabaColor.background)
    }

    // MARK: Content

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .loading:
            Spacer()
            ProgressView("Loading products…")
                .tint(ChmabaColor.purple)
            Spacer()

        case let .failed(message):
            Spacer()
            LoadStateNotice(message: message) {
                Task { await model.load() }
            }
            Spacer()

        case .ready:
            if model.visibleProducts.isEmpty {
                Spacer()
                ContentUnavailableView(
                    "No products",
                    systemImage: "shippingbox",
                    description: Text(model.search.isEmpty
                        ? "Add products to this store to start selling."
                        : "Nothing matches “\(model.search)”.")
                )
                Spacer()
            } else {
                ScrollView {
                    // `.pgrid` — two columns, 9pt gap.
                    LazyVGrid(columns: columns, spacing: 9) {
                        ForEach(model.visibleProducts) { product in
                            ProductCard(product: product, tint: tileColour(for: product)) {
                                model.add(product)
                            }
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 2)
                    .padding(.bottom, 20)
                }
            }
        }
    }

    /// The prototype's tile palette, chosen deterministically per product.
    private func tileColour(for product: ProductRead) -> Color {
        let palette = [
            Color(hex: 0xD7C0A2), Color(hex: 0xB9D7A2), Color(hex: 0xF0C986),
            Color(hex: 0xF2C1A3), Color(hex: 0xB79A83), Color(hex: 0xC99E83),
        ]
        return palette[abs(product.name.hashValue) % palette.count]
    }


}

// MARK: - Cart

struct CartSheet: View {
    @ObservedObject var model: POSViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var paymentOpen = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if model.cart.isEmpty {
                    Spacer()
                    ContentUnavailableView("Cart is empty", systemImage: "cart")
                    Spacer()
                } else {
                    List {
                        ForEach(model.cart) { line in
                            HStack(spacing: Spacing.sm) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(line.product.name)
                                        .font(.system(size: 13, weight: .semibold))
                                        .foregroundStyle(ChmabaColor.textPrimary)
                                    Text(money(line.product.price.value))
                                        .font(.system(size: 11))
                                        .foregroundStyle(ChmabaColor.textSecondary)
                                }
                                Spacer()
                                QuantityStepper(quantity: line.quantity) {
                                    model.setQuantity($0, for: line)
                                }
                                Text(money(line.lineTotal))
                                    .font(.system(size: 13))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                    .frame(width: 72, alignment: .trailing)
                            }
                        }
                    }
                    .listStyle(.plain)

                    totals
                }
            }
            .navigationTitle("Cart")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Clear", role: .destructive) { model.clearCart() }
                        .disabled(model.cart.isEmpty)
                }
            }
            .safeAreaInset(edge: .bottom) {
                if !model.cart.isEmpty {
                    ChmabaButton(
                        text: "Charge \(money(model.total, code: model.currencyCode))",
                        variant: .primary,
                        size: .large,
                        fullWidth: true,
                        trailingIcon: "arrow.right"
                    ) {
                        paymentOpen = true
                    }
                    .padding(Spacing.md)
                }
            }
            .sheet(isPresented: $paymentOpen) {
                PaymentSheet(model: model)
            }
            .sheet(item: Binding(
                get: { model.completed },
                set: { if $0 == nil { model.dismissCompleted() } }
            )) { order in
                SaleCompleteSheet(order: order, currency: model.currencyCode) {
                    model.dismissCompleted()
                    dismiss()
                }
            }
        }
    }

    private var totals: some View {
        VStack(spacing: Spacing.xxs) {
            totalRow("Subtotal", model.subtotal)
            if model.discount > 0 {
                totalRow("Discount", -model.discount, tone: Color(hex: 0xC2564B))
            }
            totalRow("Tax (10%)", model.tax)
            Divider().overlay(ChmabaColor.outline).padding(.vertical, Spacing.xxs)
            totalRow("Total", model.total, emphasised: true)
        }
        .padding(Spacing.md)
        .background(ChmabaColor.surfaceVariant)
    }

    private func totalRow(
        _ label: String,
        _ amount: Decimal,
        emphasised: Bool = false,
        tone: Color? = nil
    ) -> some View {
        HStack {
            Text(label)
                .font(.system(size: emphasised ? 15 : 13, weight: emphasised ? .semibold : .regular))
                .foregroundStyle(emphasised ? ChmabaColor.textPrimary : ChmabaColor.textSecondary)
            Spacer()
            Text(money(amount, code: model.currencyCode))
                .font(.system(size: emphasised ? 15 : 13, weight: emphasised ? .semibold : .regular))
                .foregroundStyle(tone ?? ChmabaColor.textPrimary)
        }
    }
}

struct QuantityStepper: View {
    let quantity: Int
    let onChange: (Int) -> Void

    var body: some View {
        HStack(spacing: Spacing.sm) {
            Button { onChange(quantity - 1) } label: {
                Image(systemName: "minus.circle.fill")
            }
            .disabled(quantity <= 1)

            Text("\(quantity)")
                .font(.system(size: 13))
                .foregroundStyle(ChmabaColor.textPrimary)
                .frame(minWidth: 20)

            Button { onChange(quantity + 1) } label: {
                Image(systemName: "plus.circle.fill")
            }
        }
        .tint(ChmabaColor.purple)
        .buttonStyle(.plain)
    }
}

// MARK: - Formatting

/// Currency formatting shared by the selling screens.
///
/// The code comes from the workspace's store when it is known; USD remains only as
/// the fallback for the moment before `workspaces/current` has answered.
func money(_ amount: Decimal, code: String = "USD") -> String {
    let formatter = NumberFormatter()
    formatter.numberStyle = .currency
    formatter.currencyCode = code
    formatter.locale = Locale(identifier: "en_US")
    return formatter.string(from: amount as NSDecimalNumber) ?? "\(amount)"
}

// MARK: - Payment

/// The payment sheet, from `PaymentSheet` in
/// apps/android/prototype/mobile-ui.html.
///
/// Cash takes an amount received and shows the change; KHQR completes on the amount
/// due. The prototype draws a STATIC QR glyph for KHQR with no payload and no polling
/// -- a real gap in the Android client too. It is reproduced here with that stated
/// plainly on the screen rather than dressed up as a working QR.
struct PaymentSheet: View {
    @ObservedObject var model: POSViewModel
    @Environment(\.dismiss) private var dismiss

    enum Tender: String, CaseIterable { case cash = "Cash", khqr = "KHQR" }

    @State private var tender: Tender = .cash
    @State private var received: Decimal = 0
    @State private var receivedText = ""

    private var total: Decimal { model.total }
    private var change: Decimal { max(received - total, 0) }
    private var canComplete: Bool {
        !model.submitting && (tender == .khqr || received >= total)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Payment")
                        .font(.system(size: 16, weight: .heavy))
                        .foregroundStyle(ChmabaColor.textPrimary)

                    amountDue

                    HStack(spacing: 12) {
                        tenderTile(.cash, symbol: "banknote")
                        tenderTile(.khqr, symbol: "qrcode")
                    }
                    .padding(.top, 16)

                    if tender == .cash { cashEntry } else { khqrPanel }

                    if let error = model.saleError {
                        Text(error)
                            .font(.system(size: 11.5))
                            .foregroundStyle(Color(hex: 0xC2564B))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                            .background(Color(hex: 0xFFF5F3), in: RoundedRectangle(cornerRadius: 12))
                            .padding(.top, 14)
                    }

                    ChmabaButton(
                        text: model.submitting ? "Sending…" : "Complete sale",
                        variant: .primary, size: .large, enabled: canComplete,
                        fullWidth: true, loading: model.submitting, trailingIcon: "checkmark"
                    ) {
                        Task {
                            let tendered = tender == .cash ? received : total
                            await model.submit(
                                method: tender == .cash ? "cash" : "khqr",
                                tendered: tendered
                            )
                        }
                    }
                    .padding(.top, 16)

                    Button("Back to cart") { dismiss() }
                        .buttonStyle(.plain)
                        .font(.system(size: 12.5, weight: .bold))
                        .foregroundStyle(ChmabaColor.muted)
                        .frame(maxWidth: .infinity)
                        .padding(.top, 12)
                }
                .padding(20)
            }
            .background(ChmabaColor.surface)
        }
        .presentationDetents([.medium, .large])
    }

    private var amountDue: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Amount due")
                .font(.system(size: 10.5))
                .foregroundStyle(ChmabaColor.muted)
            Text(money(total, code: model.currencyCode))
                .font(.system(size: 30, weight: .heavy))
                .tracking(-1.8)
                .foregroundStyle(ChmabaColor.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(ChmabaColor.lavender, in: RoundedRectangle(cornerRadius: 16))
        .padding(.top, 14)
    }

    private func tenderTile(_ value: Tender, symbol: String) -> some View {
        let isOn = tender == value
        return Button {
            tender = value
        } label: {
            VStack(spacing: 8) {
                Image(systemName: symbol)
                    .font(.system(size: 22))
                    .foregroundStyle(isOn ? ChmabaColor.purple : ChmabaColor.textSecondary)
                Text(value.rawValue)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(isOn ? ChmabaColor.purple : ChmabaColor.textPrimary)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 84)
            .background(isOn ? ChmabaColor.lavender : ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 16))
            .overlay {
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(isOn ? ChmabaColor.purple : ChmabaColor.border, lineWidth: isOn ? 2 : 1)
            }
        }
        .buttonStyle(.plain)
    }

    private var cashEntry: some View {
        VStack(alignment: .leading, spacing: 0) {
            ChmabaField(label: "Cash received") {
                TextField("0.00", text: $receivedText)
                    .keyboardType(.decimalPad)
                    .onChange(of: receivedText) { _, newValue in
                        received = Decimal(string: newValue) ?? 0
                    }
            }
            .padding(.top, 16)

            HStack(spacing: 7) {
                quickChip("Exact") { set(amount: total) }
                quickChip("$20") { set(amount: 20) }
                quickChip("$50") { set(amount: 50) }
                quickChip("$100") { set(amount: 100) }
            }

            if received >= total {
                HStack {
                    Text("Change due")
                        .font(.system(size: 12.5, weight: .semibold))
                        .foregroundStyle(BadgeTone.green.foreground)
                    Spacer()
                    Text(money(change, code: model.currencyCode))
                        .font(.system(size: 12.5, weight: .heavy))
                        .foregroundStyle(BadgeTone.green.foreground)
                }
                .padding(12)
                .background(BadgeTone.green.background, in: RoundedRectangle(cornerRadius: 12))
                .padding(.top, 12)
            } else {
                Text("Enter at least \(money(total, code: model.currencyCode)) to complete the sale.")
                    .font(.system(size: 10.5))
                    .foregroundStyle(ChmabaColor.faint)
                    .padding(.top, 12)
            }
        }
    }

    private var khqrPanel: some View {
        VStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 16)
                .fill(BadgeTone.green.background)
                .frame(height: 180)
                .overlay {
                    Image(systemName: "qrcode")
                        .font(.system(size: 92))
                        .foregroundStyle(BadgeTone.green.foreground)
                }
            Text("KHQR")
                .font(.system(size: 12.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textPrimary)
            Text("Ask the customer to scan to pay \(money(total, code: model.currencyCode)).")
                .font(.system(size: 11))
                .foregroundStyle(ChmabaColor.textSecondary)
                .multilineTextAlignment(.center)
            ChmabaBadge(text: "Waiting for payment", tone: .yellow, showDot: true)

            Text("The QR above is not a live payment request. Completing this sale records it as paid KHQR without confirming the transfer — the same limitation the Android client has.")
                .font(.system(size: 10))
                .foregroundStyle(ChmabaColor.faint)
                .multilineTextAlignment(.center)
                .padding(.top, 4)
        }
        .padding(.top, 16)
    }

    private func quickChip(_ label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
                .padding(.horizontal, 13)
                .frame(height: 32)
                .background(ChmabaColor.surface, in: Capsule())
                .overlay { Capsule().strokeBorder(ChmabaColor.outline, lineWidth: 1) }
        }
        .buttonStyle(.plain)
    }

    private func set(amount: Decimal) {
        received = amount
        receivedText = "\(amount)"
    }
}

/// The success sheet, from the prototype's `SuccessSheet`.
struct SaleCompleteSheet: View {
    let order: Order
    var currency: String = "USD"
    let onDone: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Circle()
                .fill(BadgeTone.green.background)
                .frame(width: 56, height: 56)
                .overlay {
                    Image(systemName: "checkmark")
                        .font(.system(size: 24, weight: .bold))
                        .foregroundStyle(BadgeTone.green.foreground)
                }

            Text("Sale complete")
                .font(.system(size: 18, weight: .heavy))
                .foregroundStyle(ChmabaColor.textPrimary)

            Text("Order \(order.orderNumber)")
                .font(.system(size: 12.5))
                .foregroundStyle(ChmabaColor.textSecondary)

            Text("\(money(order.total.value, code: order.currencyCode)) received")
                .font(.system(size: 12.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textPrimary)

            if order.changeAmount.value > 0 {
                Text("Change given · \(money(order.changeAmount.value, code: order.changeCurrencyCode ?? currency))")
                    .font(.system(size: 12.5, weight: .bold))
                    .foregroundStyle(BadgeTone.green.foreground)
            }

            Text("Receipt printing is not wired to a printer yet.")
                .font(.system(size: 10.5))
                .foregroundStyle(ChmabaColor.faint)
                .multilineTextAlignment(.center)
                .padding(.top, 2)

            ChmabaButton(
                text: "New sale", variant: .primary, size: .large,
                fullWidth: true, leadingIcon: "plus", action: onDone
            )
            .padding(.top, 10)
        }
        .padding(24)
        .presentationDetents([.medium])
    }
}

/// The scan sheet, from the prototype's ScanSheet.
///
/// The prototype offers a dark camera tile that hands off to ZXing. iOS has no
/// equivalent "launch the system scanner" contract, so the camera needs an
/// AVCaptureSession built here -- not done yet, and the tile says so rather than
/// pretending. The typed-code path works and feeds the grid search.
struct ScanSheet: View {
    let onCode: (String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var code = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Scan an item")
                        .font(.system(size: 16, weight: .heavy))
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Use the camera scanner, or type the SKU below.")
                        .font(.system(size: 11.5))
                        .foregroundStyle(ChmabaColor.muted)
                        .padding(.top, 2)

                    // The prototype's 132pt dark camera tile.
                    RoundedRectangle(cornerRadius: 16)
                        .fill(ChmabaColor.inkStrong)
                        .frame(height: 132)
                        .overlay {
                            VStack(spacing: 6) {
                                Image(systemName: "barcode.viewfinder")
                                    .font(.system(size: 30))
                                    .foregroundStyle(ChmabaColor.lime)
                                Text("Camera scanning is not built yet")
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(.white)
                                Text("iOS needs a capture session; the web POS and Android use theirs")
                                    .font(.system(size: 10.5))
                                    .foregroundStyle(Color(hex: 0xA9AAB2))
                                    .multilineTextAlignment(.center)
                            }
                            .padding(.horizontal, 16)
                        }
                        .padding(.top, 16)

                    ChmabaField(label: "SKU or barcode") {
                        TextField("e.g. SAMPLE-GENERAL-1", text: $code)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled()
                    }
                    .padding(.top, 16)

                    ChmabaButton(
                        text: "Add typed code",
                        variant: .primary, size: .large, enabled: !code.isEmpty,
                        fullWidth: true, trailingIcon: "checkmark"
                    ) {
                        onCode(code.trimmingCharacters(in: .whitespacesAndNewlines))
                        dismiss()
                    }
                    .padding(.top, 16)
                }
                .padding(20)
            }
            .background(ChmabaColor.surface)
            .navigationTitle("Scan")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }
}