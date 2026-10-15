package com.chmaba.pos.data.store

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * What an amount looks like, per currency.
 *
 * These are the branches an emulator here cannot reach: the workspace's store is USD, and moving
 * it needs a currency the company has enabled. The web's rule is the reference
 * (apps/web/src/components/ui.jsx, `formatCurrencyAmount`), so the two clients agree.
 */
class MoneyTest {

    @Test
    fun dollarsKeepTwoDecimals() {
        assertEquals("$1234.50", money(1234.5, "USD"))
        assertEquals("$0.00", money(0.0))
    }

    @Test
    fun rielIsWholeAndCarriesItsOwnSign() {
        // Rounding half up, which is what the web's Math.round does too.
        assertEquals("1,235៛", money(1234.5, "KHR"))
        assertEquals("0៛", money(0.0, "KHR"))
    }

    @Test
    fun bahtGetsItsOwnSignRatherThanADollar() {
        assertEquals("฿1234.50", money(1234.5, "THB"))
    }

    @Test
    fun anAmountReadFromTheApiIsFormattedTheSameWay() {
        assertEquals("฿12.00", money("12", "THB"))
        assertEquals("$0.00", money(null))
    }
}
