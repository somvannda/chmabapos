package com.chmaba.pos.ui.screens.orders

import com.chmaba.pos.ui.components.OrderStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the share sheet is handed when someone shares a receipt.
 *
 * The button used to say printing was not in the app, which was true of printers and false of
 * receipts: this is the text, and the things worth pinning are that every line and every figure the
 * order holds reaches it, that the totals stay in reading order, and that an optional line only
 * appears when the order actually had one.
 */
class ReceiptTextTest {

    private val order = OrderDetail(
        number = "CHM-000042",
        meta = "Walk-in · 16 Oct 2026, 10:21",
        status = OrderStatus.Paid,
        lines = listOf(
            OrderLine(name = "Iced Latte × 1", note = null, amount = "\$4.50"),
            OrderLine(name = "Sample T-Shirt × 2", note = "Large", amount = "\$24.00"),
        ),
        subtotal = "\$28.50",
        discount = null,
        tax = "\$2.85",
        total = "\$31.35",
        method = "Cash",
        paid = "\$40.00",
        change = "\$8.65",
    )

    @Test
    fun itNamesTheStoreTheOrderAndEveryLine() {
        val text = receiptText(order, "Main Counter")
        assertTrue(text.startsWith("Main Counter"))
        assertTrue(text.contains("CHM-000042"))
        assertTrue(text.contains("Iced Latte × 1"))
        assertTrue(text.contains("Sample T-Shirt × 2"))
        assertTrue(text.contains("\$24.00"))
    }

    @Test
    fun aLinesModifierTravelsWithIt() {
        // "Large" is the difference between the right shirt and the wrong one.
        assertTrue(receiptText(order, "Main Counter").contains("Large"))
    }

    @Test
    fun theTotalsStayInReadingOrder() {
        val text = receiptText(order, "Main Counter")
        val indices = listOf("Subtotal", "Tax", "Total", "Change").map { text.indexOf(it) }
        assertTrue("every total is present: " + indices, indices.all { it >= 0 })
        assertEquals("and in order", indices.sorted(), indices)
        assertTrue(text.contains("\$31.35"))
        assertTrue(text.contains("\$8.65"))
    }

    @Test
    fun theTenderAndWhatWasHandedOverAreBothThere() {
        val text = receiptText(order, "Main Counter")
        assertTrue(text.contains("Cash"))
        assertTrue(text.contains("\$40.00"))
    }

    @Test
    fun aDiscountAppearsOnlyWhenTheOrderHadOne() {
        assertFalse(receiptText(order, "Main Counter").contains("Discount"))
        val discounted = order.copy(discount = "\$3.00", total = "\$28.35")
        val text = receiptText(discounted, "Main Counter")
        assertTrue(text.contains("Discount"))
        assertTrue(text.contains("\$3.00"))
        assertTrue(text.contains("\$28.35"))
    }

    @Test
    fun noChangeLineWhenNothingWasHandedBack() {
        assertFalse(receiptText(order.copy(change = null), "Main Counter").contains("Change"))
    }

    @Test
    fun anEmptyNoteIsNotALineOfItsOwn() {
        // The fixture carries one note; a line whose note is blank must not leave a gap under it.
        val blank = order.copy(lines = listOf(OrderLine("Water × 1", note = "  ", amount = "\$1.00")))
        val text = receiptText(blank, "Main Counter")
        assertFalse(text.contains("  \n"))
        assertTrue(text.contains("Water × 1"))
    }
}
