import SwiftUI

/// Suppliers, ported from `data-screen="suppliers"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /suppliers`.
///
/// The endpoint returns a plain dict with no payment terms, no balance and no product
/// count, so rows are name + contact + active state -- which is all the prototype
/// shows anyway.
struct SuppliersView: View {
    @EnvironmentObject private var session: Session

    let onBack: () -> Void

    @State private var suppliers: [Supplier] = []
    @State private var loading = true
    @State private var error: String?
    @State private var search = ""

    private var visible: [Supplier] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !query.isEmpty else { return suppliers }
        return suppliers.filter {
            $0.name.lowercased().contains(query)
                || $0.contact.lowercased().contains(query)
        }
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
                    Text("Suppliers")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Who you buy from, and at what cost.")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer()
                ChmabaButton(text: "Add", variant: .primary, size: .small, leadingIcon: .plus) {
                    // TODO: add-supplier dialog (POST /suppliers).
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        ChmabaSearchBar(placeholder: "Search suppliers…", text: $search)
            .padding(.bottom, 12)

        if loading {
            noticeLine("Loading suppliers…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if suppliers.isEmpty {
            noticeLine("No suppliers yet.")
        } else {
            PanelList {
                let rows = visible
                if rows.isEmpty {
                    noticeLine("No suppliers match that search.").padding(16)
                } else {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, supplier in
                        ListRow(showsDivider: index < rows.count - 1) {
                            AnyView(
                                HStack(spacing: 11) {
                                    MarkChip(text: initials(supplier.name), background: tint(supplier))
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(supplier.name)
                                            .font(.system(size: 12, weight: .bold))
                                            .foregroundStyle(ChmabaColor.textPrimary)
                                            .lineLimit(1)
                                        Text(supplier.contact)
                                            .font(.system(size: 10))
                                            .foregroundStyle(ChmabaColor.faint)
                                            .lineLimit(1)
                                    }
                                }
                            )
                        } trailing: {
                            ChmabaBadge(
                                text: supplier.isActive ? "Active" : "Inactive",
                                tone: supplier.isActive ? .blue : .neutral
                            )
                        } action: {
                            // TODO: supplier detail, once it exists.
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

    private func tint(_ supplier: Supplier) -> Color {
        let palette = [Color(hex: 0xD7C0A2), Color(hex: 0xB9D7A2), Color(hex: 0xB3B6D9), Color(hex: 0xF2C1A3)]
        return palette[abs(supplier.name.hashValue) % palette.count]
    }

    private func load() async {
        if suppliers.isEmpty { loading = true }
        error = nil
        do {
            suppliers = try await APIClient.shared.get("suppliers", as: [Supplier].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load suppliers."
            loading = false
        }
    }
}
