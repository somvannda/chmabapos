package com.chmaba.pos.ui.screens.purchasing

import com.google.gson.Gson
import com.google.gson.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The body the till sends for a purchase order, pinned to a file the API's own suite also posts.
 *
 * The sale body already has this treatment (SaleBodyContractTest), and the purchase body needs it
 * more: `POST /purchases` reads a plain dict and validates it by hand (v1.py:9235), so there is no
 * schema to drift against. A field this app renames or stops sending is a 404 or a 422 at the server,
 * and nothing in the `android` job would notice. The pair notices: this pins the till's own body to
 * the golden file, and `chmabapos_api/tests/test_android_purchase_contract.py` posts that file to the
 * real endpoint.
 *
 * If this test fails, the body has changed. Either update the golden deliberately *and* check the API
 * still accepts it, or fix [purchaseBody].
 */
class PurchaseBodyContractTest {

    private val gson = Gson()

    private val body = purchaseBody(
        lines = listOf(
            PoLine(
                productId = "ad179f5c-369a-41ff-9629-f43a1ed6c39f",
                name = "Iced Latte",
                quantity = 12,
                unitCost = "1.20",
            ),
            PoLine(
                productId = "6f1d5c8e-2222-4333-8444-555566667777",
                name = "Sample T-Shirt",
                quantity = 1,
            ),
        ),
        supplierId = "5633234a-bd95-477b-af4d-89616c4ac4eb",
    )

    private fun golden(): String {
        val stream = javaClass.classLoader?.getResourceAsStream("android-purchase-body.json")
            ?: error("android-purchase-body.json is missing from the test resources")
        return stream.bufferedReader().use { it.readText() }
    }

    @Test
    fun theTillsOwnPurchaseBodyIsExactlyTheGoldenTheApiIsPutToTheTestWith() {
        // Compared as parsed JSON, so the fields and values are what is pinned, not key order.
        val sent: JsonElement = gson.fromJson(gson.toJson(body), JsonElement::class.java)
        val pinned: JsonElement = gson.fromJson(golden(), JsonElement::class.java)
        assertEquals(pinned, sent)
    }

    @Test
    fun aLineWithNoCostSendsNoneRatherThanTheWordNull() {
        // The API reads a missing unit_cost as "no cost recorded" (v1.py:9308); the *string* "null"
        // would be a cost it tried to parse.
        val json = gson.toJson(body)
        assertTrue(json.contains("\"unit_cost\":\"1.20\""))
        assertFalse(json.contains("\"unit_cost\":null"))
        assertEquals(1, Regex("\"unit_cost\"").findAll(json).count())
    }

    @Test
    fun theSupplierIsNamedAndTheBodyCarriesNoNote() {
        // The form has no note field, so the body must not grow one by accident.
        val json = gson.toJson(body)
        assertTrue(json.contains("\"supplier_id\":\"5633234a-bd95-477b-af4d-89616c4ac4eb\""))
        assertFalse(json.contains("note"))
    }
}
