import Foundation

// Request bodies for `POST /orders`, mirroring `OrderCreateRequest` (schemas.py:1763)
// and its sub-models.
//
// Constraints worth knowing, all read from the schema rather than assumed:
//
//   - `items` requires UNIQUE (product_id, variant_id) pairs (schemas.py:1788). The
//     cart already dedupes by product, so this holds.
//   - each item needs exactly one of product_id or combo_id, not both (schemas.py:1742).
//   - `tenders[].amount` is the amount TENDERED, not the amount due. Change is derived
//     server-side and comes back as a separate tender with kind == "change".
//   - `client_order_id` is the idempotency key: a repeat with the same value returns
//     the existing order rather than creating a second one.
//
// Money is sent as STRINGS. Pydantic coerces a string to Decimal, and it sidesteps the
// JSON number-versus-string ambiguity that already bit us on the read side.

struct OrderItemCreate: Encodable, Sendable {
    let productId: String
    let quantity: Int
}

struct OrderTenderCreate: Encodable, Sendable {
    /// "cash" | "khqr" | "trade_in"
    let method: String
    let currencyCode: String
    /// The amount tendered, not the amount due.
    let amount: String
}

struct OrderCreateRequest: Encodable, Sendable {
    let items: [OrderItemCreate]
    /// "cash" | "khqr"
    let paymentMethod: String
    let tenders: [OrderTenderCreate]
    /// Absolute discount off the subtotal, as the API expects.
    let discount: String
    /// Idempotency key -- regenerated per attempt so a retry after a timeout does not
    /// double-charge, but a deliberate second sale does.
    let clientOrderId: String
    /// "dine_in" | "takeaway" | "delivery"
    let orderType: String
    let customerName: String?
    let changeCurrencyCode: String?
}
