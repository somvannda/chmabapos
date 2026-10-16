package com.chmaba.pos.data.orders

import com.google.gson.Gson
import com.google.gson.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The body the till sends, pinned to a file the API's own suite also posts.
 *
 * Nothing in the `android` CI job touches the network, so a body this app sends and the API refuses
 * ships green. That is not hypothetical: `payment_method` and `tenders` were once sent together,
 * `POST /orders` refuses that pairing (v1.py:5604), and every sale failed from the app's first
 * commit until it was caught by hand on a device. Neither test catches that alone. It is caught by
 * the pair: this one proves the till's body is exactly the golden file, and
 * `chmabapos_api/tests/test_android_sale_contract.py` posts that same file to the real endpoint.
 *
 * If this test fails, the body has changed. Either update the golden deliberately *and* check the
 * API still accepts it, or fix [saleBody]. Never edit the golden to match a body nobody has put to
 * the server.
 */
class SaleBodyContractTest {

    private val gson = Gson()

    private val body = saleBody(
        lines = listOf(
            SaleLineRequest(
                productId = "ad179f5c-369a-41ff-9629-f43a1ed6c39f",
                quantity = 2,
                modifiers = listOf(
                    ModifierSelectionDto("Extra shot", "0.50"),
                    ModifierSelectionDto("Oat milk", "0.50"),
                ),
            ),
            SaleLineRequest(productId = "6f1d5c8e-2222-4333-8444-555566667777", quantity = 1),
        ),
        method = "cash",
        currencyCode = "USD",
        tendered = "20.00",
        discount = "1.00",
        customerName = "Walk-in",
        clientOrderId = "9e1c1f60-0000-0000-0000-000000000001",
    )

    private fun golden(): String {
        val stream = javaClass.classLoader?.getResourceAsStream("android-sale-body.json")
            ?: error("android-sale-body.json is missing from the test resources")
        return stream.bufferedReader().use { it.readText() }
    }

    @Test
    fun theTillsOwnBodyIsExactlyTheGoldenTheApiIsPutToTheTestWith() {
        // Compared as parsed JSON, so what is pinned is the fields and values, not the key order or
        // the spacing of the file - those are not the contract, this is.
        val sent: JsonElement = gson.fromJson(gson.toJson(body), JsonElement::class.java)
        val pinned: JsonElement = gson.fromJson(golden(), JsonElement::class.java)
        assertEquals(pinned, sent)
    }

    @Test
    fun itRecordsATenderAndNeverAPaymentMethod() {
        // The pairing the API refuses, and the reason this contract exists at all.
        val json = gson.toJson(body)
        assertFalse(json.contains("payment_method"))
        assertTrue(json.contains("\"tenders\""))
        assertEquals("USD", body.tenders?.single()?.currencyCode)
    }

    @Test
    fun aSerialTrackedLineNamesItsUnitsUnderTheApisOwnKey() {
        // Not in the golden, because the API's fixture would have to track serials to accept it;
        // the key the API reads is what is pinned here.
        val withSerials = saleBody(
            lines = listOf(
                SaleLineRequest(
                    productId = "ad179f5c-369a-41ff-9629-f43a1ed6c39f",
                    quantity = 2,
                    serialNumbers = listOf("S-1", "S-2"),
                ),
            ),
            method = "cash",
            currencyCode = "USD",
            tendered = "9.00",
        )
        assertTrue(gson.toJson(withSerials).contains("\"serial_numbers\":[\"S-1\",\"S-2\"]"))
    }
}
