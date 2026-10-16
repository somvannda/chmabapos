package com.chmaba.pos.data.orders

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the queue writes down, and what it agrees to send.
 *
 * The flush rebuilds a request out of storage, so the round trip is the whole risk: if the stored
 * JSON does not come back as the same sale, the app would replay something else - or nothing at all
 * - while having told the cashier the sale was safe. These tests put the exact body the till builds
 * through storage and back.
 */
class OfflineQueueJsonTest {

    private val gson = Gson()

    private val body = OrderCreateDto(
        items = listOf(
            OrderItemDto(
                productId = "ad179f5c-369a-41ff-9629-f43a1ed6c39f",
                quantity = 2,
                modifiers = listOf(ModifierSelectionDto("Extra shot", "0.50")),
                serialNumbers = listOf("S-1", "S-2"),
            ),
        ),
        tenders = listOf(OrderTenderDto("cash", "USD", "20.00")),
        discount = "1.00",
        customerName = "Walk-in",
        clientOrderId = "9e1c1f60-0000-0000-0000-000000000001",
    )

    @Test
    fun aStoredRequestComesBackAsTheSameSale() {
        val stored = gson.toJson(
            QueuedOrder("store-1", "9e1c1f60-0000-0000-0000-000000000001", gson.toJson(body), 1_700_000_000_000L),
        )
        val row = gson.fromJson(stored, QueuedOrder::class.java)
        assertEquals("9e1c1f60-0000-0000-0000-000000000001", row.clientOrderId)
        assertEquals("store-1", row.storeId)
        // Byte-for-byte, and then as an object: a replay is the same sale, not merely a similar one.
        assertEquals(gson.toJson(body), row.bodyJson)
        assertEquals(body, gson.fromJson(row.bodyJson, OrderCreateDto::class.java))
    }

    @Test
    fun theStoredJsonUsesTheApisOwnFieldNames() {
        val json = gson.toJson(body)
        // The API's contract rather than Kotlin's property names: this is what a replay puts on
        // the wire, and a replay that named the fields differently would be a different request.
        assertTrue(json.contains("\"client_order_id\":\"9e1c1f60-0000-0000-0000-000000000001\""))
        assertTrue(json.contains("\"product_id\":\"ad179f5c-369a-41ff-9629-f43a1ed6c39f\""))
        assertTrue(json.contains("\"serial_numbers\":[\"S-1\",\"S-2\"]"))
        assertTrue(json.contains("\"currency_code\":\"USD\""))
        assertTrue(json.contains("\"customer_name\":\"Walk-in\""))
    }

    @Test
    fun anOrderRungAtAnotherStoreIsLeftForThatStore() {
        val row = QueuedOrder("store-1", "key-1", "{}", 1L)
        assertTrue(row.belongsTo("store-1"))
        assertFalse(row.belongsTo("store-2"))
        // Nobody signed in: no store to contradict, so it stays.
        assertTrue(row.belongsTo(null))
    }

    @Test
    fun aRowThatNeverRecordedItsStoreTravelsWithWhoeverIsSignedIn() {
        assertTrue(QueuedOrder("", "key-1", "{}", 1L).belongsTo("store-9"))
    }

    @Test
    fun aRefusedRowComesBackStillKnowingWhy() {
        val refused = QueuedOrder("store-1", "key-1", "{}", 1L, "Iced Latte is out of stock")
        val stored = gson.toJson(listOf(refused))
        val type = object : com.google.gson.reflect.TypeToken<List<QueuedOrder>>() {}.type

        assertEquals("Iced Latte is out of stock", gson.fromJson<List<QueuedOrder>>(stored, type).single().lastError)
    }

    @Test
    fun aRowWrittenBeforeTheReasonExistedStillParses() {
        // The shape that is already on cashiers' devices: no lastError key at all. Gson leaves the
        // field at its default, which is what makes this change safe for a queue that is already
        // holding somebody's sale.
        val old = "[{\"storeId\":\"store-1\",\"clientOrderId\":\"key-1\",\"bodyJson\":\"{}\",\"queuedAt\":1}]"
        val type = object : com.google.gson.reflect.TypeToken<List<QueuedOrder>>() {}.type

        val rows = gson.fromJson<List<QueuedOrder>>(old, type)

        assertEquals(1, rows.size)
        assertEquals("key-1", rows.single().clientOrderId)
        assertNull(rows.single().lastError)
    }
}
