package com.chmaba.pos.data.catalog

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The shape of the serial-number request, pinned character for character.
 *
 * The endpoint mirrors `ProductSerialsSetRequest` and, unlike most of the API, carries no response
 * model and no store header requirement to lean on: `POST /products/{id}/serials` either accepts
 * the units or refuses them. A renamed key here would not be caught by anything else, and the
 * failure would look like "Could not add the serial numbers" with no clue why.
 */
class SerialsBodyTest {

    @Test
    fun numbersTravelAsTheApiNamesThem() {
        val body = ProductSerialsSetBody(
            listOf(ProductSerialWriteBody("SN-0001"), ProductSerialWriteBody("SN-0002")),
        )

        assertEquals(
            """{"serials":[{"serial_number":"SN-0001"},{"serial_number":"SN-0002"}]}""",
            Gson().toJson(body),
        )
    }

    @Test
    fun theVariantTravelsWhenOneIsChosen() {
        // A variant product keeps its stock per variant: a unit without this key is
        // counted into no balance, so the form always sends the one it picked.
        val body = ProductSerialsSetBody(listOf(ProductSerialWriteBody("SN-0004", variantId = "VAR-1")))
        assertEquals(
            """{"serials":[{"serial_number":"SN-0004","variant_id":"VAR-1"}]}""",
            Gson().toJson(body),
        )
    }

    @Test
    fun theOnlyFieldSentIsTheNumber() {
        // No imei, no warranty, no cost: the API defaults those, and sending nulls for them
        // would be noise the endpoint has to defend against.
        val body = ProductSerialsSetBody(listOf(ProductSerialWriteBody("SN-0003")))

        assertEquals("""{"serials":[{"serial_number":"SN-0003"}]}""", Gson().toJson(body))
    }
}
