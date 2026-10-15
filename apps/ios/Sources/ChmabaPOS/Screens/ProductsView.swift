import SwiftUI

/// Products, ported from `data-screen="products"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /products`.
///
/// The prototype's third tile is "Low"; the API has no low-stock count on the product
/// list, so it is derived from `on_hand` against `reorder_point` -- the same rule the
/// Android badge uses.
struct ProductsView: View {
    @EnvironmentObject private var session: Session

    let onBack: () -> Void

    @State private var products: [ProductRead] = []
    @State private var loading = true
    @State private var error: String?
    @State private var search = ""
    @State private var category: String = allCategories

    private static let allCategories = "All products"

    private var categories: [String] {
        let names = products.compactMap { $0.category?.name }
        return [Self.allCategories] + Array(Set(names)).sorted()
    }

    private var visible: [ProductRead] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return products.filter { product in
            let matchesCategory = category == Self.allCategories
                || (product.category?.name ?? "") == category
            guard matchesCategory else { return false }
            guard !query.isEmpty else { return true }
            return product.name.lowercased().contains(query)
                || product.sku.lowercased().contains(query)
                || (product.barcode?.lowercased().contains(query) ?? false)
        }
    }

    private func isLow(_ product: ProductRead) -> Bool {
        product.trackInventory && product.onHand <= Double(product.reorderPoint)
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
                    Text("Products")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Manage products and categories.")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer()
                ChmabaButton(text: "Add", variant: .primary, size: .small, leadingIcon: "plus") {
                    // TODO: the product editor, once ProductEditorView exists.
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        StatGrid(columns: 3) {
            StatTile(label: "Products", value: "\(products.count)", tone: .violet, compact: true)
            StatTile(
                label: "Active",
                value: "\(products.filter(\.isActive).count)",
                tone: .green, compact: true
            )
            StatTile(
                label: "Low",
                value: "\(products.filter(isLow).count)",
                tone: .yellow, compact: true
            )
        }

        ChmabaSearchBar(placeholder: "Search by name or SKU…", text: $search)
            .padding(.top, 12)
            .padding(.bottom, 12)

        if loading {
            noticeLine("Loading products…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if products.isEmpty {
            noticeLine("No products yet.")
        } else {
            ChipRow(items: categories, title: { $0 }, selection: $category, segmented: false)
                .padding(.bottom, 12)

            PanelList {
                let rows = visible
                if rows.isEmpty {
                    noticeLine("No products match this filter.")
                        .padding(16)
                } else {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, product in
                        ListRow(showsDivider: index < rows.count - 1) {
                            AnyView(
                                HStack(spacing: 11) {
                                    MarkChip(text: initials(product.name), background: tint(product))
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(product.name)
                                            .font(.system(size: 12, weight: .bold))
                                            .foregroundStyle(ChmabaColor.textPrimary)
                                            .lineLimit(1)
                                        Text("\(product.sku) · \(product.category?.name ?? "Uncategorised")")
                                            .font(.system(size: 10))
                                            .foregroundStyle(ChmabaColor.faint)
                                            .lineLimit(1)
                                    }
                                }
                            )
                        } trailing: {
                            VStack(alignment: .trailing, spacing: 4) {
                                Text(money(product.price.value, code: session.currencyCode))
                                    .font(.system(size: 12, weight: .heavy))
                                    .foregroundStyle(ChmabaColor.textPrimary)
                                if !product.trackInventory {
                                    ChmabaBadge(text: "Tracked off", tone: .neutral)
                                } else if product.onHand <= 0 {
                                    ChmabaBadge(text: "Out of stock", tone: .red)
                                } else if isLow(product) {
                                    ChmabaBadge(text: "Low · \(Int(product.onHand))", tone: .yellow)
                                } else {
                                    ChmabaBadge(text: "In stock", tone: .green)
                                }
                            }
                        } action: {
                            // TODO: open the editor once it exists.
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

    private func initials(_ name: String) -> String {
        name.split(separator: " ").prefix(2).compactMap { $0.first.map(String.init) }.joined().uppercased()
    }

    private func tint(_ product: ProductRead) -> Color {
        let palette = [Color(hex: 0xD7C0A2), Color(hex: 0xB9D7A2), Color(hex: 0xF0C986), Color(hex: 0xC99E83)]
        return palette[abs(product.name.hashValue) % palette.count]
    }

    private func load() async {
        if products.isEmpty { loading = true }
        error = nil
        do {
            products = try await APIClient.shared.get("products", as: [ProductRead].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load products."
            loading = false
        }
    }
}
