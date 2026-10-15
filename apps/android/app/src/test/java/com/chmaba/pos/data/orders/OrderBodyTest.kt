package com.chmaba.pos.data.orders

import com.google.gson.Gson
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The shape of a sale as the server receives it.
 *
 * `POST /orders` refuses a body that carries both `payment_method` and `tenders`
 * (v1.py:5604-5605), and the till sent both - so no sale could be recorded at all, and every
 * attempt ended at "The sale was not recorded". The field is gone from [OrderCreateDto] rather
 * than left unset, and this pins the wire format itself, because the failure is invisible on the
 * client side: the API's 400 arrives as a bare message that looks like any other refusal.
 */
class OrderBodyTest {

    private val gson = Gson()

    private fun sale() = OrderCreateDto(
        items = listOf(OrderItemDto(productId = "p1", quantity = 1, serialNumbers = listOf("SN-1"))),
        tenders = listOf(OrderTenderDto("cash", "USD", "10.99")),
        clientOrderId = "attempt-1",
    )

    @Test
    fun aSaleIsPaidWithATenderAndNeverWithABarePaymentMethod() {
        val body = gson.toJson(sale())

        assertTrue("the tender must be sent", body.contains("\"tenders\""))
        assertFalse("payment_method must not be sent alongside it", body.contains("payment_method"))
    }

    @Test
    fun theUnitsLeavingTheShelfTravelWithTheirLine() {
        val body = gson.toJson(sale())

        assertTrue(body.contains("\"serial_numbers\":[\"SN-1\"]"))
    }
}
