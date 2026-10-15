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
///
/// The embedded orders are the FULL `OrderRead` shape, not a summary -- the API
/// nests `list[OrderRead]`.
struct CustomerDetail: Codable, Sendable {
    let customer: Customer
    let ordersCount: Int
    let totalSpent: APIDecimal
    let orders: [Order]
}

/// Mirrors `OrderRead` (schemas.py:1889) for the orders list and detail.
///
/// Only the fields the screens use are declared; Codable ignores the rest, so this
/// does not have to track the 30-odd keys OrderRead carries (delivery, reservation,
/// deposit and pickup state included).
struct Order: Codable, Sendable, Identifiable {
    let id: UUID
    let orderNumber: String
    let status: String
    let customerName: String?
    let currencyCode: String
    let subtotal: APIDecimal
    let discount: APIDecimal
    let tax: APIDecimal
    let total: APIDecimal
    let amountPaid: APIDecimal
    let changeAmount: APIDecimal
    let createdAt: Date
    let paidAt: Date?
    let tenders: [OrderTender]

    /// The Android client reads the tender whose `kind == "payment"` -- a change
    /// tender is also in the list and would otherwise be mistaken for the method.
    var paymentMethod: String? {
        tenders.first { $0.kind == "payment" }?.method
    }

    var methodLabel: String { paymentMethod?.uppercased() ?? "—" }

    var tenderTone: BadgeTone {
        switch paymentMethod?.lowercased() {
        case "khqr": return .violet
        case "cash": return .green
        default: return .neutral
        }
    }

    /// Order status, mapped to the prototype's six tones. The API's status strings
    /// include a family of failure states, which the Android client collapses to
    /// "failed".
    var displayStatus: String {
        switch status.lowercased() {
        case "paid", "completed": return "Paid"
        case "pending", "payment_pending": return "Pending"
        case "pickup", "ready_for_pickup": return "Pickup"
        case "cancelled", "canceled": return "Cancelled"
        case "refunded", "partially_refunded": return "Refunded"
        case "failed", "payment_failed", "expired": return "Failed"
        default: return status.capitalized
        }
    }

    var badgeTone: BadgeTone {
        switch status.lowercased() {
        case "paid", "completed": return .green
        case "pending", "payment_pending": return .yellow
        case "pickup", "ready_for_pickup": return .violet
        case "cancelled", "canceled": return .neutral
        case "refunded", "partially_refunded": return .violet
        default: return .neutral
        }
    }

    var timeLabel: String {
        let out = DateFormatter()
        out.dateFormat = "h:mm a"
        out.locale = Locale(identifier: "en_US_POSIX")
        return out.string(from: createdAt)
    }
}

/// Mirrors `OrderTenderRead` (schemas.py:1931).
struct OrderTender: Codable, Sendable {
    let kind: String
    let method: String
    let amount: APIDecimal
    let currencyCode: String
}

// MARK: - Suppliers and purchasing
//
// Both endpoints return PLAIN DICTS, not pydantic models (v1.py:9036 and :9144), so
// there is no schema to read. The key names below come from the route bodies that
// build them. `id` is serialised with str(), so these are Strings, not UUIDs.

/// Mirrors the dict built by `list_suppliers` (v1.py:9039).
///
/// Note what is absent: no payment terms, no balance, no product count. The prototype
/// shows none of those either, which is why its rows are just name + contact.
struct Supplier: Codable, Sendable, Identifiable {
    let id: String
    let name: String
    let contactName: String?
    let phone: String?
    let email: String?
    let isActive: Bool

    var contact: String {
        contactName ?? phone ?? email ?? "No contact details"
    }
}

/// One line of a purchase order's snapshot (v1.py:9186).
struct PurchaseLine: Codable, Sendable {
    let productId: String?
    let productName: String?
    let sku: String?
    let variantId: String?
    let variantName: String?
    let quantity: Int
    let unitCost: String?

    var displayName: String { productName ?? sku ?? "Item" }
}

/// Mirrors the dict built by `list_purchases` (v1.py:9149).
struct PurchaseOrder: Codable, Sendable, Identifiable {
    let id: String
    let poNumber: String
    let status: String
    let supplier: String?
    let note: String?
    let items: [PurchaseLine]
    let createdAt: String?
    let orderedAt: String?
    let receivedAt: String?

    /// The payload carries no total, but each line DOES carry a unit cost, so the
    /// total is derivable. Returns nil when no line has a cost rather than showing a
    /// misleading zero -- the Android client shows "—" here because it never
    /// multiplies the lines out.
    var computedTotal: Decimal? {
        var total = Decimal.zero
        var priced = false
        for line in items {
            guard let raw = line.unitCost, let cost = Decimal(string: raw) else { continue }
            total += cost * Decimal(line.quantity)
            priced = true
        }
        return priced ? total : nil
    }

    var lineCount: Int { items.count }

    var badgeTone: BadgeTone {
        switch status.lowercased() {
        case "received": return .green
        case "partial": return .yellow
        case "draft": return .neutral
        default: return .blue
        }
    }

    var displayStatus: String { status.capitalized }

    /// "4 Oct" from the ISO date. Same prefix-parsing approach the reports rows use.
    var dateLabel: String {
        let raw = orderedAt ?? createdAt ?? ""
        guard raw.count >= 10 else { return "—" }
        let parser = DateFormatter()
        parser.dateFormat = "yyyy-MM-dd"
        parser.locale = Locale(identifier: "en_US_POSIX")
        guard let date = parser.date(from: String(raw.prefix(10))) else { return "—" }
        let out = DateFormatter()
        out.dateFormat = "d MMM"
        out.locale = Locale(identifier: "en_US_POSIX")
        return out.string(from: date)
    }
}
