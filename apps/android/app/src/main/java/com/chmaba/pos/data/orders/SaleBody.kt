package com.chmaba.pos.data.orders

/**
 * The request body a sale is sent as.
 *
 * This lives apart from the till so it can be held to the API's contract by tests that need no
 * screen, no device and no network: a golden file of [saleBody]'s own output
 * (app/src/test/resources/android-sale-body.json) is pinned by SaleBodyContractTest, and the API's
 * own suite posts that same file to the real `POST /orders`.
 *
 * That pairing exists because of a specific failure. The till once sent `payment_method` *and*
 * `tenders` together; the API refuses a body carrying both (v1.py:5604), so every sale failed from
 * the app's first commit until it was caught by hand on a device. Nothing in the `android` CI job
 * touches the network, so no test could see it. Now a body the API refuses cannot come back
 * without a test failing.
 *
 * A tender is what the till records rather than a bare `payment_method`: it names the currency the
 * cash was counted in, which a payment method alone cannot, and the web POS sends tenders alone.
 *
 * The money arguments arrive already formatted to two places, because the API's decimal fields
 * travel as strings and formatting is the till's business, not this function's.
 */
fun saleBody(
    lines: List<SaleLineRequest>,
    /** The method for this sale's single tender: "cash" or "khqr". */
    method: String,
    currencyCode: String,
    /** What the cashier actually took. The API derives the change from it. */
    tendered: String,
    discount: String = "0.00",
    customerName: String? = null,
    clientOrderId: String? = null,
): OrderCreateDto = OrderCreateDto(
    items = lines.map { line ->
        OrderItemDto(
            productId = line.productId,
            quantity = line.quantity,
            modifiers = line.modifiers,
            serialNumbers = line.serialNumbers,
        )
    },
    tenders = listOf(OrderTenderDto(method, currencyCode, tendered)),
    discount = discount,
    customerName = customerName,
    clientOrderId = clientOrderId,
)

/**
 * One line of a sale, as the API needs it.
 *
 * The till's own cart lines are mapped onto this, so the wire shape has no opinion about tiles,
 * colours or optiosheets.
 */
data class SaleLineRequest(
    val productId: String?,
    val quantity: Int,
    val modifiers: List<ModifierSelectionDto> = emptyList(),
    /**
     * The units leaving the shelf, for a serial-tracked product. The API requires exactly one per
     * unit on such a sale and rejects the request without them (v1.py:5711).
     */
    val serialNumbers: List<String>? = null,
)
