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
        guard !query.isEmpty else { return products }
        return products.filter {
            $0.name.lowercased().contains(query)
                || $0.sku.lowercased().contains(query)
                || ($0.barcode?.lowercased().contains(query) ?? false)
        }
    }

    var itemCount: Int { cart.reduce(0) { $0 + $1.quantity } }
    var subtotal: Decimal { cart.reduce(Decimal.zero) { $0 + $1.lineTotal } }

    /// 10% tax, matching the Android client's `TAX_RATE = 0.10`.
    /// TODO: read this from store settings once the API exposes it; a hard-coded
    /// rate is fine for a dev slice and wrong for a real till.
    var tax: Decimal { subtotal * Decimal(0.10) }
    var total: Decimal { subtotal + tax }

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

    func clearCart() { cart.removeAll() }
}

struct POSView: View {
    @EnvironmentObject private var session: Session
    @StateObject private var model = POSViewModel()
    @State private var cartOpen = false

    private let columns = [GridItem(.adaptive(minimum: 140), spacing: Spacing.sm)]

    var body: some View {
        VStack(spacing: 0) {
            topBar
            content
            if !model.cart.isEmpty { cartBar }
        }
        .background(ChmabaColor.background)
        .task { if case .loading = model.state { await model.load() } }
        .sheet(isPresented: $cartOpen) { CartSheet(model: model) }
    }

    // MARK: Top bar

    /// Mirrors the Android POS top bar: brand mark, register status, search.
    private var topBar: some View {
        VStack(spacing: Spacing.sm) {
            HStack(alignment: .center) {
                ChmabaLogo(chipSize: 28, wordmark: false)
                    .padding(.trailing, Spacing.xxs)

                VStack(alignment: .leading, spacing: 2) {
                    ChmabaBadge(text: "Register 01 is ready", tone: .green, showDot: true)
                    Text("Make a sale")
                        .font(.system(size: 12))
                        .foregroundStyle(ChmabaColor.textSecondary)
                }

                Spacer()

                Button {
                    Task { await session.signOut() }
                } label: {
                    Image(systemName: "rectangle.portrait.and.arrow.right")
                        .foregroundStyle(ChmabaColor.grey600)
                }
                .buttonStyle(.plain)
            }

            ChmabaSearchBar(placeholder: "Search products or scan a barcode", text: $model.search)
        }
        .padding(Spacing.md)
        .background(ChmabaColor.surface)
        .overlay(alignment: .bottom) {
            Rectangle().fill(ChmabaColor.outline).frame(height: 1)
        }
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
                    LazyVGrid(columns: columns, spacing: Spacing.sm) {
                        ForEach(model.visibleProducts) { product in
                            ProductCard(product: product, tint: tileColour(for: product)) {
                                model.add(product)
                            }
                        }
                    }
                    .padding(Spacing.md)
                }
            }
        }
    }

    private var cartBar: some View {
        HStack(spacing: Spacing.md) {
            Button {
                cartOpen = true
            } label: {
                HStack(spacing: Spacing.xs) {
                    ZStack {
                        Circle().fill(.white.opacity(0.2)).frame(width: 28, height: 28)
                        Text("\(model.itemCount)")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundStyle(.white)
                    }
                    Text("View cart")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(.white)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)

            Text(money(model.total))
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(.white)
        }
        .padding(.horizontal, Spacing.md)
        .frame(height: 56)
        .background(ChmabaColor.purple, in: RoundedRectangle(cornerRadius: 12))
        .padding(Spacing.md)
    }

    /// Deterministic tint per product, mirroring the Android tile palette.
    private func tileColour(for product: ProductRead) -> Color {
        let palette: [Color] = [
            ChmabaColor.purple, ChmabaColor.violet, ChmabaColor.warning,
            ChmabaColor.success, ChmabaColor.grey600,
        ]
        return palette[abs(product.name.hashValue) % palette.count]
    }
}

// MARK: - Cart

struct CartSheet: View {
    @ObservedObject var model: POSViewModel
    @Environment(\.dismiss) private var dismiss

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
                        text: "Charge \(money(model.total))",
                        variant: .primary,
                        size: .large,
                        fullWidth: true
                    ) {
                        // TODO: POST /orders. The cart totals are correct but nothing
                        // is submitted yet -- the order payload needs reading from
                        // schemas.py first rather than guessing it.
                    }
                    .padding(Spacing.md)
                }
            }
        }
    }

    private var totals: some View {
        VStack(spacing: Spacing.xxs) {
            totalRow("Subtotal", model.subtotal)
            totalRow("Tax (10%)", model.tax)
            Divider().overlay(ChmabaColor.outline).padding(.vertical, Spacing.xxs)
            totalRow("Total", model.total, emphasised: true)
        }
        .padding(Spacing.md)
        .background(ChmabaColor.surfaceVariant)
    }

    private func totalRow(_ label: String, _ amount: Decimal, emphasised: Bool = false) -> some View {
        HStack {
            Text(label)
                .font(.system(size: emphasised ? 15 : 13, weight: emphasised ? .semibold : .regular))
                .foregroundStyle(emphasised ? ChmabaColor.textPrimary : ChmabaColor.textSecondary)
            Spacer()
            Text(money(amount))
                .font(.system(size: emphasised ? 15 : 13, weight: emphasised ? .semibold : .regular))
                .foregroundStyle(ChmabaColor.textPrimary)
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
/// TODO: take the code from the workspace's store (a `StoreRead` is fetched at
/// sign-in); USD is a dev default, not the real configuration.
func money(_ amount: Decimal, code: String = "USD") -> String {
    let formatter = NumberFormatter()
    formatter.numberStyle = .currency
    formatter.currencyCode = code
    formatter.locale = Locale(identifier: "en_US")
    return formatter.string(from: amount as NSDecimalNumber) ?? "\(amount)"
}
