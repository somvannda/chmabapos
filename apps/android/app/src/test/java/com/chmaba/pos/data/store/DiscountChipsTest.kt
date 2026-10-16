package com.chmaba.pos.data.store

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The discount sheet's one-tap amounts, per currency.
 *
 * The same problem as the till's cash chips, in a second place: 1/5/10 is a dollar-sized discount,
 * and a riel store was offered amounts nobody discounts by. The values here are a judgement about
 * what a shop discounts with, not something the API states - so they are one table, easy to change.
 */
class DiscountChipsTest {

    @Test
    fun dollarsKeepTheAmountsThatWereAlwaysThere() {
        assertEquals(listOf(1.0, 5.0, 10.0), discountChips("USD"))
    }

    @Test
    fun rielIsDiscountedInThousands() {
        assertEquals(listOf(500.0, 1_000.0, 5_000.0), discountChips("KHR"))
    }

    @Test
    fun bahtIsDiscountedInBaht() {
        assertEquals(listOf(20.0, 50.0, 100.0), discountChips("THB"))
    }

    @Test
    fun everyAmountIsWholeAndPositiveInEveryCurrency() {
        for (currency in listOf("USD", "THB", "KHR", "XYZ")) {
            val amounts = discountChips(currency)
            assertTrue(currency, amounts.isNotEmpty())
            for (amount in amounts) {
                assertTrue(currency + " " + amount + " is not whole", amount % 1.0 == 0.0)
                assertTrue(currency + " " + amount + " is not positive", amount > 0.0)
            }
            assertEquals(currency, amounts.size, amounts.toSet().size)
        }
    }

    @Test
    fun anUnknownCurrencyFallsBackToTheSameAmountsAsItsFormatting() {
        assertEquals(discountChips("USD"), discountChips("XYZ"))
    }

    @Test
    fun theAmountsAgreeWithTheCurrencyTheyWillBeFormattedIn() {
        // A chip's label comes from money(), so a whole amount must render without decimals in
        // every currency - otherwise the chip says one thing and sets another.
        for (currency in listOf("USD", "THB", "KHR")) {
            for (amount in discountChips(currency)) {
                val label = money(amount, currency)
                // money() adds separators and a sign, so compare the digits it renders.
                val rendered = label.filter { it.isDigit() }
                assertTrue(currency + " label " + label, rendered.contains(amount.toInt().toString()))
            }
        }
    }
}
