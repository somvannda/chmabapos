import SwiftUI

/// Adjust how many units are on hand. Writes `PATCH /inventory/{productId}`.
///
/// **The quantity is the new counted total, not a change.** The API computes
/// `difference = quantity - existing.on_hand` (`v1.py:5352`), so a screen that treated the
/// field as "how many to add" would set stock to the number added and quietly lose the rest.
/// The label says "New count on hand" and the current figure is shown above it for that
/// reason.
struct StockAdjustView: View {
    let item: InventoryItem
    let onDone: () -> Void
    let onBack: () -> Void

    @State private var quantity = ""
    @State private var reason = "manual_adjustment"
    @State private var saving = false
    @State private var error: String?
    /// Set when the API answered with an approval request instead of the new balance.
    @State private var pendingApproval = false

    private var canSave: Bool {
        guard !saving else { return false }
        // A variant product keeps its units on the variants, so writing the
        // product's own balance would create stock no screen counts. This screen
        // has no variant picker; the Android and web apps do.
        guard item.variants.isEmpty else { return false }
        guard !reason.trimmingCharacters(in: .whitespaces).isEmpty else { return false }
        guard let value = Double(quantity), value >= 0 else { return false }
        return true
    }

    var body: some View {
        VStack(spacing: 0) {
            appBar
            PageBody(topPadding: 2) { form }
        }
        .background(ChmabaColor.background)
        .onAppear { quantity = Self.units(item.stockUnits) }
    }

    private var appBar: some View {
        AppBar(onBack: onBack) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Adjust stock")
                    .font(.system(size: 18, weight: .heavy))
                    .tracking(-0.05)
                    .foregroundStyle(ChmabaColor.textPrimary)
                Text("\(item.productName) · \(item.sku)")
                    .font(.system(size: 11))
                    .foregroundStyle(ChmabaColor.muted)
                    .lineLimit(1)
            }
        }
    }

    @ViewBuilder
    private var form: some View {
        if !item.variants.isEmpty {
            Text("This product is sold in variants, so its units live on the variants. Adjust each one from the Android or web app.")
                .font(.system(size: 10.5))
                .foregroundStyle(ChmabaColor.faint)
                .padding(.bottom, 10)
        }
        PanelList {
            ListRow(showsDivider: false) {
                AnyView(
                    VStack(alignment: .leading, spacing: 2) {
                        Text("On hand now")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(ChmabaColor.textPrimary)
                        Text("The count this replaces.")
                            .font(.system(size: 10))
                            .foregroundStyle(ChmabaColor.faint)
                    }
                )
            } trailing: {
                Text(Self.units(item.stockUnits))
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundStyle(ChmabaColor.textPrimary)
            } action: {}
        }
        .padding(.bottom, 14)

        VStack(alignment: .leading, spacing: 6) {
            Text("New count on hand")
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            TextField("0", text: $quantity)
                .font(.system(size: 13))
                .keyboardType(.decimalPad)
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
        }
        .padding(.bottom, 12)

        VStack(alignment: .leading, spacing: 6) {
            Text("Reason")
                .font(.system(size: 10.5, weight: .bold))
                .foregroundStyle(ChmabaColor.textSecondary)
            TextField("manual_adjustment", text: $reason)
                .font(.system(size: 13))
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .padding(.horizontal, 12)
                .frame(height: 44)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
            Text("Kept in the activity log beside the count this replaces.")
                .font(.system(size: 10))
                .foregroundStyle(ChmabaColor.faint)
        }
        .padding(.bottom, 12)

        if let error {
            Text(error)
                .font(.system(size: 11))
                .lineSpacing(2)
                .foregroundStyle(BadgeTone.red.foreground)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 4)
        }

        if pendingApproval {
            Text("A change this large needs the owner's approval. It has been sent, and stock "
                 + "will move once they accept it.")
                .font(.system(size: 11))
                .lineSpacing(2)
                .foregroundStyle(BadgeTone.yellow.foreground)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 4)
        }

        ChmabaButton(
            text: "Save count",
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

    /// Whole units print without a decimal point; a weighed count keeps its fraction.
    static func units(_ value: Double) -> String {
        value == value.rounded() ? String(Int(value)) : String(format: "%.3f", value)
    }

    private struct Payload: Encodable {
        let quantity: String
        let reason: String
    }

    private func save() async {
        saving = true
        error = nil
        pendingApproval = false

        let payload = Payload(
            quantity: quantity.trimmingCharacters(in: .whitespaces),
            reason: reason.trimmingCharacters(in: .whitespaces)
        )

        do {
            _ = try await APIClient.shared.patch(
                "inventory/\(item.productId.uuidString)",
                body: payload,
                as: InventoryItem.self
            )
            onDone()
        } catch let apiError as APIError {
            // A large write-off is GATED: the API answers with an approval request rather than
            // the new balance, so the response is not an InventoryRead and decoding fails. That
            // is a successful submission, not an error, and saying so is better than showing a
            // failure for something that has in fact been sent for approval.
            if case .decoding = apiError {
                pendingApproval = true
            } else {
                error = apiError.errorDescription
            }
        } catch {
            self.error = "Could not save the count."
        }
        saving = false
    }
}
