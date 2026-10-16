import SwiftUI

/// The product editor — create a product, or edit one. Ported from the prototype's
/// `data-screen="product-edit"`.
///
/// Writes `POST /products` (create) or `PATCH /products/{id}` (edit). Money and tax are sent
/// as STRINGS, not doubles: the API takes a `Decimal`, and `"4.50"` survives the round trip
/// where a binary double could arrive as `4.499999`.
///
/// Deliberately not included, and each has its own endpoint rather than being missing:
///
///   - **Product image.** `POST /products/{id}/image` takes an upload, which needs photo
///     picking and multipart. A text field for a URL would be a worse lie than an omission.
///   - **Variants.** `POST /products/{id}/variants` is a separate resource with its own stock.
///     The prototype shows an "Add" affordance here that opens that flow; there is no such flow
///     on iOS yet.
///   - **In stock on edit.** `ProductUpdateRequest` carries no stock field, because stock moves
///     through inventory adjustments rather than by typing a number over it. The field is
///     therefore only offered when creating, where it is `opening_stock`.
struct ProductEditorView: View {
    @EnvironmentObject private var session: Session

    /// Nil creates; a value edits.
    let existing: ProductRead?
    let categories: [CategoryRead]
    let onDone: (ProductRead) -> Void
    let onBack: () -> Void

    @State private var name = ""
    @State private var sku = ""
    @State private var price = ""
    @State private var costPrice = ""
    @State private var taxRate = ""
    @State private var barcode = ""
    @State private var descriptionText = ""
    @State private var categoryId: UUID?
    @State private var unit = "each"
    @State private var trackInventory = true
    @State private var trackSerials = false
    @State private var openingStock = "0"
    @State private var reorderPoint = "10"
    @State private var saving = false
    @State private var error: String?

    private static let units = ["each", "kg", "g", "l", "ml", "m", "box", "pack"]

    private var isEditing: Bool { existing != nil }

    private var canSave: Bool {
        guard !saving else { return false }
        guard !name.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        guard !sku.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        guard let value = Double(price), value > 0 else { return false }
        return true
    }

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 2) { form }
        }
        .background(ChmabaColor.background)
        .onAppear(perform: prime)
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            VStack(alignment: .leading, spacing: 2) {
                Text(isEditing ? "Edit \(existing!.name)" : "New product")
                    .font(.system(size: 18, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                    .lineLimit(1)
                Text(isEditing ? "Update product details." : "Add something to sell.")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
            }
        }
    }

    @ViewBuilder
    private var form: some View {
        HStack(spacing: 10) {
            textField("Name", $name)
            textField("SKU", $sku)
        }
        HStack(spacing: 10) {
            textField("Price", $price, keyboard: .decimalPad)
            textField("Cost price", $costPrice, keyboard: .decimalPad)
        }
        HStack(spacing: 10) {
            // Blank means "use the store's own rate", which is what the API's null means.
            textField("Tax %", $taxRate, placeholder: "Store default", keyboard: .decimalPad)
            menuField("Unit", selection: $unit, options: Self.units.map { ($0, $0) })
        }
        textField("Barcode", $barcode, placeholder: "Scan or type")
        menuField(
            "Category",
            selection: Binding(
                get: { categoryId?.uuidString ?? "" },
                set: { categoryId = UUID(uuidString: $0) }
            ),
            options: [( "", "Uncategorised")] + categories.map { ($0.id.uuidString, $0.name) }
        )

        VStack(alignment: .leading, spacing: 6) {
            Text("Description")
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            TextField("Optional", text: $descriptionText, axis: .vertical)
                .font(.system(size: 13))
                .lineLimit(2...4)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
        }
        .padding(.bottom, 12)

        if !isEditing {
            HStack(spacing: 10) {
                textField("In stock", $openingStock, keyboard: .decimalPad)
                textField("Reorder point", $reorderPoint, keyboard: .numberPad)
            }
        }

        toggleRow("Track inventory", isOn: $trackInventory)
        toggleRow("Track serials / IMEI", isOn: $trackSerials)

        if let error {
            Text(error)
                .font(.system(size: 11))
                .lineSpacing(2)
                .foregroundStyle(BadgeTone.red.foreground)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 8)
        }

        ChmabaButton(
            text: isEditing ? "Save product" : "Create product",
            variant: .primary,
            size: .large,
            enabled: canSave,
            fullWidth: true,
            loading: saving
        ) {
            Task { await save() }
        }
        .padding(.top, 16)
        .padding(.bottom, 8)
    }

    // MARK: Pieces

    private func prime() {
        guard let existing else { return }
        name = existing.name
        sku = existing.sku
        price = "\(existing.price.value)"
        costPrice = existing.costPrice.map { "\($0.value)" } ?? ""
        taxRate = existing.taxRate.map { "\($0.value)" } ?? ""
        barcode = existing.barcode ?? ""
        descriptionText = existing.description ?? ""
        categoryId = existing.category?.id
        trackInventory = existing.trackInventory
        trackSerials = existing.trackSerials
        unit = existing.unit
    }

    private func textField(_ label: String, _ binding: Binding<String>,
                           placeholder: String? = nil,
                           keyboard: UIKeyboardType = .default) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            TextField(placeholder ?? label, text: binding)
                .font(.system(size: 13))
                .keyboardType(keyboard)
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 12)
    }

    private func menuField(_ label: String, selection: Binding<String>,
                           options: [(String, String)]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            Menu {
                ForEach(options, id: \.0) { value, title in
                    Button(title) { selection.wrappedValue = value }
                }
            } label: {
                HStack {
                    Text(options.first { $0.0 == selection.wrappedValue }?.1
                         ?? options.first?.1 ?? "—")
                        .font(.system(size: 12.5))
                        .foregroundStyle(ChmabaColor.textPrimary)
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    ChmabaIconView(icon: .chevronDown, size: 12, color: ChmabaColor.faint)
                }
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 12)
    }

    private func toggleRow(_ label: String, isOn: Binding<Bool>) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 12.5))
                .foregroundStyle(ChmabaColor.textPrimary)
            Spacer(minLength: 0)
            Toggle("", isOn: isOn)
                .labelsHidden()
                .tint(ChmabaColor.purple)
        }
        .padding(.vertical, 6)
    }

    // MARK: Save

    private struct Payload: Encodable {
        let name: String
        let sku: String
        let price: String
        let costPrice: String?
        let taxRate: String?
        let barcode: String?
        let description: String?
        let categoryId: UUID?
        let unit: String
        let trackInventory: Bool
        let trackSerials: Bool
        // Create-only fields. `ProductUpdateRequest` ignores unknown keys, but they are sent
        // as nil when editing anyway so the intent is readable.
        let openingStock: String?
        let reorderPoint: Int?
    }

    private func save() async {
        saving = true
        error = nil

        let trimmedBarcode = barcode.trimmingCharacters(in: .whitespaces)
        let trimmedDescription = descriptionText.trimmingCharacters(in: .whitespacesAndNewlines)
        let payload = Payload(
            name: name.trimmingCharacters(in: .whitespaces),
            sku: sku.trimmingCharacters(in: .whitespaces),
            price: price.trimmingCharacters(in: .whitespaces),
            costPrice: costPrice.trimmingCharacters(in: .whitespaces).isEmpty
                ? nil : costPrice.trimmingCharacters(in: .whitespaces),
            taxRate: taxRate.trimmingCharacters(in: .whitespaces).isEmpty
                ? nil : taxRate.trimmingCharacters(in: .whitespaces),
            barcode: trimmedBarcode.isEmpty ? nil : trimmedBarcode,
            description: trimmedDescription.isEmpty ? nil : trimmedDescription,
            categoryId: categoryId,
            unit: unit,
            trackInventory: trackInventory,
            trackSerials: trackSerials,
            openingStock: isEditing ? nil : openingStock,
            reorderPoint: isEditing ? nil : Int(reorderPoint)
        )

        do {
            let saved: ProductRead
            if let existing {
                saved = try await APIClient.shared.patch(
                    "products/\(existing.id.uuidString)", body: payload, as: ProductRead.self
                )
            } else {
                saved = try await APIClient.shared.post(
                    "products", body: payload, as: ProductRead.self
                )
            }
            onDone(saved)
        } catch let apiError as APIError {
            // A duplicate SKU or barcode comes back as a 409/400 with the API's own words,
            // which are more useful here than a generic failure.
            error = apiError.errorDescription
        } catch {
            self.error = "Could not save the product."
        }
        saving = false
    }
}
