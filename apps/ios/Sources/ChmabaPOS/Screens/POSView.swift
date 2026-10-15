import SwiftUI

/// The selling surface: product grid, search, and a cart.
///
/// Deliberately mirrors the Android client's mobile layout (`POSScreen.kt` puts the
/// cart in a bottom bar + sheet rather than the web's fixed 320pt sidebar). Same
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

    // MARK: Loading

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

    // MARK: Cart

    var itemCount: Int { cart.reduce(0) { $0 + $1.quantity } }

    var subtotal: Decimal { cart.reduce(Decimal.zero) { $0 + $1.lineTotal } }

    /// 10% tax, matching the Android client's `TAX_RATE = 0.10`.
    /// TODO: take this from the store/company settings once the API exposes it --
    /// a hard-coded rate is fine for a dev slice and wrong for production.
    var tax: Decimal { (subtotal * Decimal(0.10)) }

    var total: Decimal { subtotal + tax }

    func add(_ product: ProductRead) {
        guard product.onHand > 0 || !product.trackInventory else { return }
        if let index = cart.firstIndex(where: { $0.id == product.id }) {
            // Respect stock, exactly as the Android cart does.
            if !product.trackInventory || Decimal(cart[index].quantity) < Decimal(product.onHand) {
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
            // onHand is a Double from the API; compare in Int to avoid Decimal<->Int
            // conversion gymnastics (Decimal has no Int initializer).
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
            navigationBar
            content
            if !model.cart.isEmpty { cartBar }
        }
        .background(ChmabaColor.background)
        .task { if case .loading = model.state { await model.load() } }
        .sheet(isPresented: $cartOpen) {
            CartSheet(model: model)
        }
    }

    // MARK: Sections

    private var navigationBar: some View {
        VStack(spacing: Spacing.sm) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(session.user?.fullName ?? "Till")
                        .font(.headline)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Ready to sell")
                        .font(.caption)
                        .foregroundStyle(ChmabaColor.textSecondary)
                }
                Spacer()
                Button {
                    Task { await session.signOut() }
                } label: {
                    Image(systemName: "rectangle.portrait.and.arrow.right")
                        .font(.body.weight(.medium))
                }
                .tint(ChmabaColor.grey600)
            }

            HStack(spacing: Spacing.xs) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(ChmabaColor.grey400)
                TextField("Search products or scan a barcode", text: $model.search)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                if !model.search.isEmpty {
                    Button {
                        model.search = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(ChmabaColor.grey400)
                    }
                }
            }
            .padding(.horizontal, Spacing.sm)
            .frame(height: 44)
            .background(ChmabaColor.surfaceVariant, in: RoundedRectangle(cornerRadius: 12))
        }
        .padding(Spacing.md)
        .background(ChmabaColor.surface)
        .overlay(alignment: .bottom) {
            Divider().overlay(ChmabaColor.outline)
        }
    }

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .loading:
            Spacer()
            ProgressView("Loading products…")
            Spacer()

        case let .failed(message):
            Spacer()
            VStack(spacing: Spacing.sm) {
                Image(systemName: "wifi.exclamationmark")
                    .font(.largeTitle)
                    .foregroundStyle(BadgeTone.danger.foreground)
                Text(message)
                    .font(.subheadline)
                    .multilineTextAlignment(.center)
                    .foregroundStyle(ChmabaColor.textSecondary)
                    .padding(.horizontal, Spacing.lg)
                Button("Try again") { Task { await model.load() } }
                    .buttonStyle(.borderedProminent)
                    .tint(ChmabaColor.purple)
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
                            ProductTile(product: product) { model.add(product) }
                        }
                    }
                    .padding(Spacing.md)
                }
            }
        }
    }

    private var cartBar: some View {
        Button {
            cartOpen = true
        } label: {
            HStack {
                ZStack {
                    Circle().fill(.white.opacity(0.2)).frame(width: 32, height: 32)
                    Text("\(model.itemCount)")
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(.white)
                }
                Text("View cart")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
                Text(money(model.total))
                    .font(.headline.monospacedDigit())
                    .foregroundStyle(.white)
            }
            .padding(.horizontal, Spacing.md)
            .frame(height: 56)
        }
        .background(ChmabaColor.purple)
        .padding(Spacing.md)
    }
}

/// 140x180 product card, matching the guide's grid spec.
struct ProductTile: View {
    let product: ProductRead
    let onTap: () -> Void

    private var isOutOfStock: Bool { product.trackInventory && product.onHand <= 0 }

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: 0) {
                ZStack {
                    Rectangle().fill(tileColour)
                    Text(initials)
                        .font(.title2.weight(.bold))
                        .foregroundStyle(.white.opacity(0.9))
                }
                .frame(height: 100)

                VStack(alignment: .leading, spacing: 2) {
                    Text(product.name)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(ChmabaColor.textPrimary)
                        .lineLimit(2, reservesSpace: true)
                    Text(money(product.price.value))
                        .font(.subheadline.monospacedDigit())
                        .foregroundStyle(ChmabaColor.textPrimary)
                    if product.trackInventory {
                        Text(isOutOfStock ? "Out of stock" : "\(Int(product.onHand)) left")
                            .font(.caption2)
                            .foregroundStyle(isOutOfStock ? BadgeTone.danger.foreground : ChmabaColor.textSecondary)
                    }
                }
                .padding(Spacing.xs)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(height: 180)
            .background(ChmabaColor.surface)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12).strokeBorder(ChmabaColor.outline, lineWidth: 1)
            )
            .opacity(isOutOfStock ? 0.5 : 1)
        }
        .buttonStyle(.plain)
        .disabled(isOutOfStock)
    }

    private var initials: String {
        product.name.split(separator: " ").prefix(2)
            .compactMap { $0.first.map(String.init) }
            .joined()
            .uppercased()
    }

    /// Deterministic tint per product so the grid looks intentional without images.
    /// Mirrors the Android client's tile palette approach.
    private var tileColour: Color {
        let palette: [Color] = [ChmabaColor.purple, ChmabaColor.violet, ChmabaColor.warning,
                                ChmabaColor.success, ChmabaColor.grey600]
        let index = abs(product.name.hashValue) % palette.count
        return palette[index]
    }
}

// MARK: - Cart

struct CartSheet: View {
    @ObservedObject var model: POSViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var checkoutOpen = false

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
                                    Text(line.product.name).font(.subheadline.weight(.semibold))
                                    Text(money(line.product.price.value))
                                        .font(.caption)
                                        .foregroundStyle(ChmabaColor.textSecondary)
                                }
                                Spacer()
                                QuantityStepper(
                                    quantity: line.quantity,
                                    onChange: { model.setQuantity($0, for: line) }
                                )
                                Text(money(line.lineTotal))
                                    .font(.subheadline.monospacedDigit())
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
                    Button {
                        checkoutOpen = true
                    } label: {
                        Text("Charge \(money(model.total))")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .frame(height: 48)
                    }
                    .background(ChmabaColor.purple, in: RoundedRectangle(cornerRadius: 12))
                    .foregroundStyle(.white)
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
                .font(emphasised ? .headline : .subheadline)
                .foregroundStyle(emphasised ? ChmabaColor.textPrimary : ChmabaColor.textSecondary)
            Spacer()
            Text(money(amount))
                .font(emphasised ? .headline.monospacedDigit() : .subheadline.monospacedDigit())
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
                .font(.subheadline.monospacedDigit())
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
/// The Android client carries a currency code on the session; this is the iOS
/// equivalent, defaulting to USD until the store's own currency is wired through.
func money(_ amount: Decimal, code: String = "USD") -> String {
    let formatter = NumberFormatter()
    formatter.numberStyle = .currency
    formatter.currencyCode = code
    formatter.locale = Locale(identifier: "en_US")
    return formatter.string(from: amount as NSDecimalNumber) ?? "\(amount)"
}
