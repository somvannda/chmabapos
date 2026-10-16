import SwiftUI

/// Customers, ported from `data-screen="customers"` in
/// apps/android/prototype/mobile-ui.html, reading `GET /customers?search=`.
///
/// Where the prototype's rows show an order count and lifetime spend, this shows the
/// loyalty points instead: `CustomerRead` carries no counts, and inventing them would
/// be the one thing the Android client explicitly refuses to do.
struct CustomersView: View {
    @EnvironmentObject private var session: Session

    let onBack: () -> Void
    var onOpenCustomer: (Customer) -> Void

    @State private var customers: [Customer] = []
    @State private var loading = true
    @State private var error: String?
    @State private var search = ""

    private var visible: [Customer] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !query.isEmpty else { return customers }
        return customers.filter {
            $0.name.lowercased().contains(query)
                || ($0.phone?.lowercased().contains(query) ?? false)
                || ($0.email?.lowercased().contains(query) ?? false)
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
                    Text("Customers")
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Text("Shared across your stores.")
                        .font(.system(size: 11))
                        .foregroundStyle(ChmabaColor.muted)
                }
                Spacer()
                ChmabaButton(text: "Add", variant: .primary, size: .small, leadingIcon: .plus) {
                    // TODO: add-customer dialog, once the write endpoint is wired.
                }
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        ChmabaSearchBar(placeholder: "Search by name or phone…", text: $search)
            .padding(.bottom, 12)

        if loading {
            noticeLine("Loading customers…")
        } else if let error {
            LoadStateNotice(message: error) { Task { await load() } }
                .frame(maxWidth: .infinity)
                .padding(.top, 20)
        } else if customers.isEmpty {
            noticeLine("No customers yet.")
        } else {
            PanelList {
                let rows = visible
                if rows.isEmpty {
                    noticeLine("No customers match that search.").padding(16)
                } else {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, customer in
                        ListRow(showsDivider: index < rows.count - 1) {
                            AnyView(
                                HStack(spacing: 11) {
                                    Circle()
                                        .fill(tint(customer))
                                        .frame(width: 36, height: 36)
                                        .overlay {
                                            Text(initials(customer.name))
                                                .font(.system(size: 11, weight: .heavy))
                                                .foregroundStyle(Color(hex: 0x44424A))
                                        }
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(customer.name)
                                            .font(.system(size: 12, weight: .bold))
                                            .foregroundStyle(ChmabaColor.textPrimary)
                                            .lineLimit(1)
                                        Text(customer.contact)
                                            .font(.system(size: 10))
                                            .foregroundStyle(ChmabaColor.faint)
                                            .lineLimit(1)
                                    }
                                }
                            )
                        } trailing: {
                            Text("\(intPoints(customer)) pts")
                                .font(.system(size: 12, weight: .heavy))
                                .foregroundStyle(ChmabaColor.textPrimary)
                        } action: {
                            onOpenCustomer(customer)
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

    private func intPoints(_ customer: Customer) -> Int {
        NSDecimalNumber(decimal: customer.points.value).intValue
    }

    private func initials(_ name: String) -> String {
        name.split(separator: " ").prefix(2).compactMap { $0.first.map(String.init) }.joined().uppercased()
    }

    private func tint(_ customer: Customer) -> Color {
        let palette = [Color(hex: 0xD7C0A2), Color(hex: 0xB9D7A2), Color(hex: 0xB3B6D9), Color(hex: 0xF2C1A3)]
        return palette[abs(customer.name.hashValue) % palette.count]
    }

    private func load() async {
        if customers.isEmpty { loading = true }
        error = nil
        do {
            customers = try await APIClient.shared.get("customers", as: [Customer].self)
            loading = false
        } catch let apiError as APIError {
            error = apiError.errorDescription
            loading = false
        } catch {
            self.error = "Could not load customers."
            loading = false
        }
    }
}
