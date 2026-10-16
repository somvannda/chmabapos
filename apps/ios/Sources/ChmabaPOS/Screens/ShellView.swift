import SwiftUI

/// The signed-in shell: a bottom-nav tab set whose "More" tab is a grouped
/// destination list.
///
/// Mirrors `MainShell.kt`, which pairs a 64dp bottom bar with a drawer. The drawer is
/// reproduced here as the More *tab* rather than a swipe-out, because that is what
/// the prototype shows (`data-nav`) and it removes the hand-rolled nested back-unwind
/// the Android client needs.
struct ShellView: View {
    @EnvironmentObject private var session: Session

    @State private var tab: MainTab = .home
    @State private var destination: MoreDestination?
    @State private var notice: String?
    @AppStorage(AppAppearance.storageKey) private var appearanceRaw = AppAppearance.light.rawValue

    private var storeName: String { session.workspaceName ?? "Your store" }
    private var companyName: String { session.companyName ?? "" }

    var body: some View {
        VStack(spacing: 0) {
            if let notice {
                ShellNotice(message: notice) { self.notice = nil }
            }

            ZStack {
                switch tab {
                case .home:
                    DashboardView(
                        onOpenMenu: { tab = .more },
                        onNewSale: { tab = .pos },
                        onOpenProducts: { open(.products) },
                        onOpenOrders: { tab = .orders }
                    )
                case .pos:
                    POSView()
                case .orders:
                    OrdersView { _ in
                        // TODO: the order detail screen.
                        notice = "Opening an order isn't in the iOS app yet. Use the web POS for it."
                    }
                case .more:
                    moreTab
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            BottomNav(tab: $tab)
        }
        .background(ChmabaColor.background)
    }

    // MARK: More

    @ViewBuilder
    private var moreTab: some View {
        if let destination {
            destinationScreen(destination)
        } else {
            moreList
        }
    }

    private var moreList: some View {
        PageBody(topPadding: 20) {
            Text("More")
                .font(.system(size: 20, weight: .heavy))
                .tracking(-0.05)
                .foregroundStyle(ChmabaColor.textPrimary)

            Text(companyName.isEmpty ? storeName : "\(storeName) · \(companyName)")
                .font(.system(size: 12.5))
                .foregroundStyle(ChmabaColor.muted)
                .padding(.top, 2)
                .padding(.bottom, 8)

            ForEach(MoreGroup.allCases, id: \.self) { group in
                Text(group.title)
                    .font(.system(size: 9.5, weight: .heavy))
                    .tracking(1.1)
                    .textCase(.uppercase)
                    .foregroundStyle(ChmabaColor.muted)
                    .padding(.top, 18)
                    .padding(.bottom, 8)

                PanelList {
                    let items = group.items
                    ForEach(Array(items.enumerated()), id: \.element) { _, item in
                        ListRow(showsDivider: false) {
                            AnyView(
                                HStack(spacing: 11) {
                                    RoundedRectangle(cornerRadius: 11, style: .continuous)
                                        .fill(ChmabaColor.lavender)
                                        .frame(width: 34, height: 34)
                                        .overlay {
                                            ChmabaIconView(icon: item.icon, size: 17, color: ChmabaColor.purple)
                                        }
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(item.title)
                                            .font(.system(size: 12.5, weight: .bold))
                                            .foregroundStyle(ChmabaColor.textPrimary)
                                        Text(item.subtitle)
                                            .font(.system(size: 10))
                                            .foregroundStyle(ChmabaColor.faint)
                                    }
                                }
                            )
                        } trailing: {
                            ChmabaIconView(icon: .chevronRight, size: 13, color: ChmabaColor.ghost)
                        } action: {
                            open(item)
                        }
                    }
                }
            }

            Button {
                Task { await session.signOut() }
            } label: {
                HStack(spacing: 11) {
                    ChmabaIconView(icon: .lock, size: 15, color: Color(hex: 0xC2564B))
                    Text("Sign out")
                        .font(.system(size: 12.5, weight: .bold))
                }
                .foregroundStyle(Color(hex: 0xC2564B))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.vertical, 14)
                .background(ChmabaColor.surface, in: RoundedRectangle(cornerRadius: 16))
                .overlay {
                    RoundedRectangle(cornerRadius: 16).strokeBorder(ChmabaColor.border, lineWidth: 1)
                }
            }
            .buttonStyle(.plain)
            .padding(.top, 18)
        }
    }

    private func open(_ destination: MoreDestination) {
        self.destination = destination
    }

    /// Screens that exist render; the rest say so plainly rather than pretending.
    /// `PlaceholderScreen` in the Android client does exactly this.
    @ViewBuilder
    private func destinationScreen(_ destination: MoreDestination) -> some View {
        switch destination {
        case .products:
            ProductsView(onBack: { self.destination = nil })
        case .categories:
            CategoriesView(onBack: { self.destination = nil })
        case .customers:
            CustomersView(
                onBack: { self.destination = nil },
                onOpenCustomer: { _ in
                    // TODO: CustomerDetailView, once the detail screen exists.
                    notice = "Opening a customer isn't in the iOS app yet. Use the web POS for it."
                }
            )
        case .inventory:
            InventoryView(onBack: { self.destination = nil })
        case .reports:
            ReportsView(onBack: { self.destination = nil })
        case .purchasing:
            PurchasingView(onBack: { self.destination = nil })
        case .suppliers:
            SuppliersView(onBack: { self.destination = nil })
        default:
            PlaceholderScreen(
                title: destination.title,
                onBack: { self.destination = nil }
            )
        }
    }
}

/// The yellow dismissible banner from `ShellNotice` in the Android shell.
struct ShellNotice: View {
    let message: String
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 10) {
            Text(message)
                .font(.system(size: 11.5))
                .foregroundStyle(ChmabaColor.textPrimary)
                .frame(maxWidth: .infinity, alignment: .leading)
            Button("Dismiss", action: onDismiss)
                .buttonStyle(.plain)
                .font(.system(size: 11.5, weight: .bold))
                .foregroundStyle(ChmabaColor.purple)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color(hex: 0xFFF6DF))
    }
}

/// The Android client's `PlaceholderScreen`: "Being ported".
struct PlaceholderScreen: View {
    let title: String
    let onBack: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            AppBar {
                HStack(spacing: 10) {
                    IconButton(icon: .chevronLeft, action: onBack)
                    Text(title)
                        .font(.system(size: 20, weight: .heavy))
                        .tracking(-0.05)
                        .foregroundStyle(ChmabaColor.textPrimary)
                    Spacer()
                }
            }

            PageBody {
                POSPanel {
                    RoundedRectangle(cornerRadius: 15, style: .continuous)
                        .fill(ChmabaColor.lavender)
                        .frame(width: 46, height: 46)
                        .overlay {
                            ChmabaIconView(icon: .package, size: 20, color: ChmabaColor.purple)
                        }
                    Text("Being ported")
                        .font(.system(size: 14, weight: .heavy))
                        .foregroundStyle(ChmabaColor.textPrimary)
                        .padding(.top, 12)
                    Text("This screen is designed and approved in the prototype; the iOS build lands next.")
                        .font(.system(size: 11.5))
                        .foregroundStyle(ChmabaColor.textSecondary)
                        .padding(.top, 4)
                }
            }
        }
    }
}

// MARK: - More destinations

enum MoreDestination: String, CaseIterable, Hashable {
    case products, categories, customers, inventory, purchasing, suppliers
    case reports, team, activity, billing, settings, help

    var title: String {
        switch self {
        case .products: return "Products"
        case .categories: return "Categories"
        case .customers: return "Customers"
        case .inventory: return "Inventory"
        case .purchasing: return "Purchasing"
        case .suppliers: return "Suppliers"
        case .reports: return "Reports"
        case .team: return "Team"
        case .activity: return "Activity"
        case .billing: return "Billing & plans"
        case .settings: return "Settings"
        case .help: return "Help & support"
        }
    }

    var subtitle: String {
        switch self {
        case .products: return "Catalog, variants, serials"
        case .categories: return "Organise the catalog"
        case .customers: return "Profiles, orders, loyalty"
        case .inventory: return "Levels, adjust, receive"
        case .purchasing: return "Purchase orders"
        case .suppliers: return "Who you buy from"
        case .reports: return "Sales, margin, breakdowns"
        case .team: return "Members, roles, invites"
        case .activity: return "Everything your team changed"
        case .billing: return "Live plan pricing"
        case .settings: return "Store, tax, payments"
        case .help: return "Guides and the AI assistant"
        }
    }

    /// Lucide icons, matching the Android client's More/drawer destinations.
    var icon: ChmabaIcon {
        switch self {
        case .products: return .package
        case .categories: return .tag
        case .customers: return .users
        case .inventory: return .boxes
        case .purchasing: return .truck
        case .suppliers: return .store
        case .reports: return .barChart
        case .team: return .userPlus
        case .activity: return .clock
        case .billing: return .creditCard
        case .settings: return .sliders
        case .help: return .message
        }
    }
}

/// The prototype's four More groups, in order.
enum MoreGroup: String, CaseIterable, Hashable {
    case selling, stock, business, account

    var title: String {
        switch self {
        case .selling: return "Selling"
        case .stock: return "Stock"
        case .business: return "Business"
        case .account: return "Account"
        }
    }

    var items: [MoreDestination] {
        switch self {
        case .selling: return [.products, .categories, .customers]
        case .stock: return [.inventory, .purchasing, .suppliers]
        case .business: return [.reports, .team, .activity]
        case .account: return [.billing, .settings, .help]
        }
    }
}
