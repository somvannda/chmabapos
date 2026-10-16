package com.chmaba.pos.data.store

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The till's one-tap cash amounts, per currency.
 *
 * These are presets for the whole field, so a chip below a typical sale is worse than no chip: the
 * cashier taps it, the sale cannot complete, and the field has to be retyped. The rule is that every
 * chip is a note someone would actually hand over for the kind of sale this store makes.
 */
class CashChipsTest {

    @Test
    fun dollarsKeepTheAmountsThatWereAlwaysThere() {
        assertEquals(listOf(20.0, 50.0, 100.0), cashChips("USD"))
    }

    @Test
    fun rielIsOfferedInRielNotesRatherThanDollarSizedOnes() {
        // 20/50/100 riel is real money and useless money: the notes start at 100 and a sale is
        // paid with thousands.
        assertEquals(listOf(10_000.0, 20_000.0, 50_000.0), cashChips("KHR"))
    }

    @Test
    fun bahtIsOfferedInBahtNotes() {
        assertEquals(listOf(100.0, 500.0, 1_000.0), cashChips("THB"))
    }

    @Test
    fun anUnknownCurrencyGetsTheSameAmountsAsItsFormatting() {
        assertEquals(cashChips("USD"), cashChips("XYZ"))
    }

    @Test
    fun everyChipIsAWholeNumberOfUnitsWorthTapping() {
        for (currency in listOf("USD", "THB", "KHR", "XYZ")) {
            val chips = cashChips(currency)
            assertTrue(currency, chips.isNotEmpty())
            for (chip in chips) {
                assertTrue("$currency chip $chip is not whole", chip % 1.0 == 0.0)
                assertTrue("$currency chip $chip is not positive", chip > 0.0)
            }
            // Descending or ascending does not matter, but they must not repeat.
            assertEquals(currency, chips.size, chips.toSet().size)
        }
    }

    @Test
    fun exactTakesThePrecisionTheCurrencyIsCountedIn() {
        // Riel has no sub-unit in practice; a field holding 20500.00 cannot be handed over.
        assertEquals("20500", exactCash(20500.0, "KHR"))
        assertEquals("4.95", exactCash(4.95, "USD"))
        assertEquals("150.00", exactCash(150.0, "THB"))
        // And it agrees with the sign the amount is displayed with.
        assertEquals(money(20500.0, "KHR").filter { it.isDigit() || it == ',' }, "20,500")
    }
}
