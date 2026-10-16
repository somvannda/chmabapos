package com.chmaba.pos.data.store

import com.google.gson.Gson
import com.google.gson.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The body the till sends to refund an order, pinned to a file the API's own suite also posts.
 *
 * The third body to get this treatment, after the sale and the purchase, and the one where a mistake
 * costs money in the wrong direction. `POST /orders/{id}/refund` matches each returned line to the
 * order's line by `(product_id, variant_id)` (v1.py:7113), and a line that arrives without its
 * variant matches nothing - so it is refunded as *nothing* while the rest of the refund succeeds and
 * the endpoint still answers 201. A cashier has no way to see that shortfall, which is why it is
 * pinned here rather than trusted.
 *
 * If this test fails, the body has changed. Either update the golden deliberately *and* check the API
 * still acts on it, or fix `RefundItemBody`.
 */
class RefundBodyContractTest {

    private val gson = Gson()

    /** What the app sends for an order of two lines, one of which sold a variant. */
    private val body = RefundCreateBody(
        items = listOf(
            RefundItemBody(productId = "ad179f5c-369a-41ff-9629-f43a1ed6c39f", quantity = 2.0),
            RefundItemBody(
                productId = "6f1d5c8e-2222-4333-8444-555566667777",
                quantity = 1.0,
                variantId = "c3b1d0e2-1111-4222-8333-444455556666",
            ),
        ),
    )

    private fun golden(): String {
        val stream = javaClass.classLoader?.getResourceAsStream("android-refund-body.json")
            ?: error("android-refund-body.json is missing from the test resources")
        return stream.bufferedReader().use { it.readText() }
    }

    @Test
    fun theTillsOwnRefundBodyIsExactlyTheGoldenTheApiIsPutToTheTestWith() {
        // Compared as parsed JSON, so the fields and values are pinned, not the key order.
        val sent: JsonElement = gson.fromJson(gson.toJson(body), JsonElement::class.java)
        val pinned: JsonElement = gson.fromJson(golden(), JsonElement::class.java)
        assertEquals(pinned, sent)
    }

    @Test
    fun aVariantLineCarriesItsVariantAndAPlainOneDoesNot() {
        // The whole safety of a refund: a line without its variant returns nothing at all.
        val json = gson.toJson(body)
        assertTrue(json.contains("\"variant_id\":\"c3b1d0e2-1111-4222-8333-444455556666\""))
        assertFalse(json.contains("\"variant_id\":null"))
        assertEquals(1, Regex("\"variant_id\"").findAll(json).count())
    }

    @Test
    fun theOrderIsRefundedTheWayItCameInAndWithNoReason() {
        // "original" puts the money back the way it arrived; the app asks for no reason.
        val json = gson.toJson(body)
        assertTrue(json.contains("\"method\":\"original\""))
        assertFalse(json.contains("reason"))
    }
}
