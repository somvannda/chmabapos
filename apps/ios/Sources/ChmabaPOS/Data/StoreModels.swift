import Foundation

// Store DTOs for the customers and inventory screens, mirroring
// chmabapos_api/app/schemas.py.

// MARK: - Inventory

/// Mirrors `InventoryRead` (schemas.py:1405).
struct InventoryItem: Codable, Sendable, Identifiable {
    let storeId: UUID
    let productId: UUID
    let productName: String
    let sku: String
    let price: APIDecimal
    /// Null when the product has no cost recorded. The UI must NOT treat a missing
    /// cost as zero when valuing stock -- the Android client only counts priced rows.
    let costPrice: APIDecimal?
    let onHand: Double
    let reorderPoint: Int
    let status: Status
    let trackSerials: Bool
    let image: String?

    var id: UUID { productId }

    enum Status: String, Codable, Sendable {
        case healthy, low, out
    }

    /// Value of this line, or nil when the cost basis is unknown.
    var stockValue: Decimal? {
        guard let cost = costPrice else { return nil }
        return cost.value * Decimal(onHand)
    }

    var badgeTone: BadgeTone {
        switch status {
        case .healthy: return .green
        case .low: return .yellow
        case .out: return .red
        }
    }
}

// MARK: - Customers

/// Mirrors `CustomerRead` (schemas.py:1671).
///
/// NOTE this carries no order count or lifetime spend -- those exist only on
/// `CustomerDetailRead`. The prototype's list rows show both; the Android client
/// shows points instead, because points are the only figure the list actually
/// returns. Same choice here.
struct Customer: Codable, Sendable, Identifiable {
    let id: UUID
    let name: String
    let phone: String?
    let email: String?
    let notes: String?
    let points: APIDecimal
    let isActive: Bool
    let createdAt: Date

    /// The prototype shows "phone · N orders"; with no count available this is the
    /// contact line the Android client falls back to.
    var contact: String {
        phone ?? email ?? "No contact details"
    }
}

/// Mirrors `CustomerDetailRead` (schemas.py:1682).
struct CustomerDetail: Codable, Sendable {
    let customer: Customer
    let ordersCount: Int
    let totalSpent: APIDecimal
    let orders: [OrderSummary]
}

/// The subset of `OrderRead` the customer detail's recent-orders list needs.
struct OrderSummary: Codable, Sendable, Identifiable {
    let id: UUID
    let orderNumber: String?
    let status: String?
    let total: APIDecimal
    let currencyCode: String?
    let createdAt: Date?

    var displayNumber: String { orderNumber.map { $0 } ?? "—" }

    var badgeTone: BadgeTone {
        switch status?.lowercased() {
        case "paid", "completed": return .green
        case "pending", "payment_pending": return .yellow
        case "cancelled": return .neutral
        case "refunded": return .violet
        default: return .neutral
        }
    }

    var displayStatus: String {
        switch status?.lowercased() {
        case "paid", "completed": return "Paid"
        case "pending", "payment_pending": return "Pending"
        case "cancelled": return "Cancelled"
        case "refunded": return "Refunded"
        default: return status?.capitalized ?? "—"
        }
    }
}
