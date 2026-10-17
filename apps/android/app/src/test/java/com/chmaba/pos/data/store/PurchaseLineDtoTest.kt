package com.chmaba.pos.data.store

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * The line snapshots a purchase order carries, pinned to the keys the API writes.
 *
 * `GET /purchases` returns each order's `items` as the dict `v1.py` stored at creation
 * (`snapshot.append(...)`), not as a response schema. So a renamed key would not be a compile error
 * anywhere: it would be a detail screen with blank lines and a cost that silently vanished.
 */
class PurchaseLineDtoTest {

    private val gson = Gson()

    private fun parse(json: String): List<PurchaseLineDto> =
        gson.fromJson(json, object : TypeToken<List<PurchaseLineDto>>() {}.type)

    @Test
    fun theKeysTheApiWritesAreTheOnesTheAppReads() {
        // Copied from the snapshot shape in v1.py, with one plain line.
        val rows = parse(
            """[{"product_id":"ad179f5c-369a-41ff-9629-f43a1ed6c39f","product_name":"Iced Latte",
               "sku":"COF-001","variant_id":null,"variant_name":null,"quantity":3,
               "unit_cost":"1.20"}]""".trimIndent(),
        )
        assertEquals(1, rows.size)
        assertEquals("Iced Latte", rows[0].productName)
        assertEquals("COF-001", rows[0].sku)
        assertEquals(3.0, rows[0].quantity, 0.0)
        assertEquals("1.20", rows[0].unitCost)
        assertNull(rows[0].variantName)
    }

    @Test
    fun aVariantLineKeepsItsVariant() {
        val rows = parse(
            """[{"product_id":"p","product_name":"Shoe","sku":"SH-1","variant_id":"v1",
               "variant_name":"Large","quantity":2,"unit_cost":null}]""".trimIndent(),
        )
        assertEquals("Large", rows[0].variantName)
        assertNull(rows[0].unitCost)
    }

    @Test
    fun aWeighedQuantityKeepsItsFraction() {
        // Stock quantities are decimals on the server; 1.5 kg must not arrive as 1.
        val rows = parse(
            """[{"product_id":"p","product_name":"Coffee","sku":"C-1","quantity":1.5}]"""
        )
        assertEquals(1.5, rows[0].quantity, 0.0)
    }
}
