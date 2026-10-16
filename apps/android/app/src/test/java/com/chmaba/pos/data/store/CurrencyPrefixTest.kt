package com.chmaba.pos.data.store

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The sign an input may carry before the figure the cashier is typing.
 *
 * The till's cash-received and discount fields prefixed a hardcoded "$", so a store that does not
 * use dollars showed the wrong currency on the one control where an amount is being entered - and
 * contradicted the total directly above it, which [money] renders correctly. The rule here
 * follows [money] rather than inventing a second one.
 */
class CurrencyPrefixTest {

    @Test
    fun thePrefixAgreesWithTheTotalShownFromTheSameCurrency() {
        assertEquals("$", currencyPrefix("USD"))
        assertEquals("฿", currencyPrefix("THB"))
    }

    @Test
    fun thePrefixIsOnlySomethingTheCurrencyWritesBeforeANumber() {
        // Riel writes its sign after the figure ("1,234៛"), so nothing can precede a typed
        // amount; the field's placeholder already carries the sign. Prefixing it would read
        // "៛1,234៛".
        assertEquals("", currencyPrefix("KHR"))
    }

    @Test
    fun anUnknownCurrencyIsPrefixedExactlyAsMoneyFormatsIt() {
        assertEquals("$", currencyPrefix("XYZ"))
    }

    @Test
    fun noPrefixEverContradictsTheAmountBesideIt() {
        for (currency in listOf("USD", "THB", "KHR", "XYZ")) {
            val prefix = currencyPrefix(currency)
            val amount = money(1234.5, currency)
            assertTrue(
                "for " + currency + ": '" + prefix + "' does not lead '" + amount + "'",
                prefix.isEmpty() || amount.startsWith(prefix),
            )
        }
    }
}
