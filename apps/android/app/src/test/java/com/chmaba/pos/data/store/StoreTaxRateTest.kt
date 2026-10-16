package com.chmaba.pos.data.store

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * What the tax field will and will not accept.
 *
 * The till charges this rate on every sale, so a typo here is a wrong price on the next receipt -
 * and the API would answer 422 naming `service_tax_rate`, a field the person typing has never seen.
 * The rule is checked before the request instead.
 */
class StoreTaxRateTest {

    @Test
    fun aPlainNumberIsAccepted() {
        assertNull(taxRateProblem("10"))
        assertNull(taxRateProblem("0"))
        assertNull(taxRateProblem("7.5"))
        assertNull(taxRateProblem("12.25"))
    }

    @Test
    fun SurroundingSpaceIsForgiven() {
        assertNull(taxRateProblem("  10  "))
    }

    @Test
    fun anEmptyBoxSaysWhatToDoRatherThanSendingNothing() {
        // Empty would clear the rate on the server, which is not the same as zero.
        assertEquals("A tax rate is needed. Enter 0 for none.", taxRateProblem(""))
        assertEquals("A tax rate is needed. Enter 0 for none.", taxRateProblem("   "))
    }

    @Test
    fun wordsAndPercentSignsAreRefused() {
        // "10%" is what a person types when they mean ten per cent.
        assertEquals("The tax rate has to be a number, like 10 or 7.5.", taxRateProblem("ten"))
        assertEquals("The tax rate has to be a number, like 10 or 7.5.", taxRateProblem("10%"))
    }

    @Test
    fun aNegativeRateIsRefused() {
        assertEquals("A tax rate cannot be negative.", taxRateProblem("-1"))
    }

    @Test
    fun MoreThanTwoDecimalPlacesIsRefused() {
        assertEquals("Use at most two decimal places.", taxRateProblem("7.125"))
    }
}
