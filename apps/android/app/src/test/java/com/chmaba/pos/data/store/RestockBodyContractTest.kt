package com.chmaba.pos.data.store

import com.google.gson.Gson
import com.google.gson.JsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The body the Inventory screen sends to receive stock, pinned to a file the API's own suite posts.
 *
 * The fourth body to get this treatment, after the sale, the purchase and the refund - and the one
 * with the most optional parts, which is exactly why it needs it. `POST /inventory/{id}/restock`
 * takes a positive delta plus fields that each change what the receipt *means*: `variant_id` decides
 * whose balance moves, `supplier` becomes the movement's own wording, and `serial_numbers` is what a
 * serial-tracked product cannot be received without at all.
 *
 * A renamed key here would not be a type error anywhere. It would be a silent refusal - the API
 * answers "Provide one serial per unit received" - or stock landing on a balance no sale draws on.
 * That is the same shape of failure that hid a short refund until it was pinned.
 *
 * If this test fails, the body has changed. Either update the golden deliberately *and* check the API
 * still acts on it, or fix `InventoryRestockBody`.
 */
class RestockBodyContractTest {

    private val gson = Gson()

    /** A serial-tracked product received into one of its variants, from a named supplier. */
    private val body = InventoryRestockBody(
        quantity = 2,
        variantId = "c3b1d0e2-1111-4222-8333-444455556666",
        supplier = "Contract Supplier",
        reference = "DN-0001",
        unitCost = "4.50",
        serialNumbers = listOf("SN-0001", "SN-0002"),
    )

    private fun golden(): String {
        val stream = javaClass.classLoader?.getResourceAsStream("android-restock-body.json")
            ?: error("android-restock-body.json is missing from the test resources")
        return stream.bufferedReader().use { it.readText() }
    }

    @Test
    fun theScreensOwnReceiveBodyIsExactlyTheGoldenTheApiIsPutToTheTestWith() {
        // Compared as parsed JSON, so the fields and values are pinned, not the key order.
        val sent: JsonElement = gson.fromJson(gson.toJson(body), JsonElement::class.java)
        val pinned: JsonElement = gson.fromJson(golden(), JsonElement::class.java)
        assertEquals(pinned, sent)
    }

    @Test
    fun theSerialsTravelUnderTheNameTheApiRequires() {
        // One per unit, under the key the handler reads. A rename here is a receipt the API refuses
        // outright, with a message about serials rather than about the field that was renamed.
        val json = gson.toJson(body)
        assertTrue(json.contains("\"serial_numbers\":[\"SN-0001\",\"SN-0002\"]"))
        assertEquals(1, Regex("\"serial_numbers\"").findAll(json).count())
    }

    @Test
    fun theVariantTravelsWithTheUnits() {
        // Without it the API writes the product's own balance, which for this product is not the
        // number a sale draws on - the same fault #824 and #827 were about.
        val json = gson.toJson(body)
        assertTrue(
            json.contains("\"variant_id\":\"c3b1d0e2-1111-4222-8333-444455556666\""),
        )
    }

    @Test
    fun noReasonIsSentSoTheApiNamesTheMovementFromTheSupplier() {
        // The API derives the movement's wording: `reason` when given, else "Received from
        // {supplier}", else "Stock received". Sending a flat "received" would throw the supplier away.
        val json = gson.toJson(body)
        assertFalse(json.contains("\"reason\""))
        assertTrue(json.contains("\"supplier\":\"Contract Supplier\""))
        assertTrue(json.contains("\"reference\":\"DN-0001\""))
        assertTrue(json.contains("\"unit_cost\":\"4.50\""))
    }

    @Test
    fun aReceiptWithoutTheOptionalPartsSendsOnlyWhatItHas() {
        // Nulls are omitted rather than sent, so a plain receipt is a plain body.
        val bare = InventoryRestockBody(quantity = 1)
        assertEquals("""{"quantity":1}""", gson.toJson(bare))
    }
}
