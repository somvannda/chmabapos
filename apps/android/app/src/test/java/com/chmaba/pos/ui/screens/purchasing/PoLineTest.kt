package com.chmaba.pos.ui.screens.purchasing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * How the order sheet's lines behave while they are being collected.
 *
 * The API has always taken a list - `PurchaseCreateBody.items` - and the form could only ever send
 * one, so a delivery of five things became five orders. This is what building the list means, and it
 * is pure so it can be held here rather than by tapping a sheet on a device.
 */
class PoLineTest {

    private val latte = PoLine(productId = "p-1", name = "Iced Latte", quantity = 2)
    private val shirt = PoLine(productId = "p-2", name = "T-Shirt", quantity = 1)

    @Test
    fun addingAProductTwiceAddsToItsQuantityRatherThanRepeatingIt() {
        val once = withLine(emptyList(), latte)
        val twice = withLine(once, latte.copy(quantity = 3))

        assertEquals(1, twice.size)
        assertEquals(5, twice.single().quantity)
        assertEquals("Iced Latte", twice.single().name)
    }

    @Test
    fun aDifferentProductBecomesItsOwnLine() {
        val lines = withLine(withLine(emptyList(), latte), shirt)

        assertEquals(listOf("p-1", "p-2"), lines.map { it.productId })
        assertEquals(listOf(2, 1), lines.map { it.quantity })
    }

    @Test
    fun removingTakesTheWholeLineAndLeavesTheRest() {
        val lines = withLine(withLine(emptyList(), latte), shirt)

        val left = withoutLine(lines, "p-1")

        assertEquals(listOf("p-2"), left.map { it.productId })
    }

    @Test
    fun removingSomethingThatIsNotThereChangesNothing() {
        val lines = withLine(emptyList(), latte)

        assertEquals(lines, withoutLine(lines, "p-9"))
    }

    @Test
    fun aLineWithoutACostKeepsTheCostItsLineAlreadyHad() {
        val lines = withLine(emptyList(), latte.copy(unitCost = "1.20"))
        val merged = withLine(lines, latte)

        assertEquals(1, merged.size)
        assertEquals(4, merged.single().quantity)
        assertEquals("1.20", merged.single().unitCost)
    }

    @Test
    fun aLineWithACostReplacesTheOneAlreadyThere() {
        val lines = withLine(emptyList(), latte.copy(unitCost = "1.20"))
        val merged = withLine(lines, latte.copy(unitCost = "1.50"))

        assertEquals("1.50", merged.single().unitCost)
    }

    @Test
    fun theCostFieldAcceptsWhatTheApiDoesAndNothingElse() {
        // Empty is a real answer: the API stores no cost at all for that line.
        assertNull(unitCostProblem(""))
        assertNull(unitCostProblem("   "))
        assertNull(unitCostProblem("0"))
        assertNull(unitCostProblem("1.20"))
        assertEquals("The unit cost has to be a number, or left empty.", unitCostProblem("free"))
        assertEquals("A unit cost cannot be negative.", unitCostProblem("-1"))
        assertEquals("Use at most two decimal places.", unitCostProblem("1.205"))
    }
}
