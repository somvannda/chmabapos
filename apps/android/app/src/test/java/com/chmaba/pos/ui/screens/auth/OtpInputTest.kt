package com.chmaba.pos.ui.screens.auth

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * What the code field accepts (issue #744).
 *
 * It is one input, not six. Six separate boxes raced the IME's chunks and lost characters: a code of
 * 047881 reached the API as "781", and before that as "60534" for 060534. Nothing positional is left
 * to get wrong, and what remains is pinned here - digits only, at most six, and a leading zero kept.
 */
class OtpInputTest {

    @Test
    fun aCodeIsKeptWholeLeadingZeroIncluded() {
        assertEquals("047881", otpDigits("047881"))
        assertEquals("060534", otpDigits("060534"))
    }

    @Test
    fun onlyDigitsSurvive() {
        assertEquals("047881", otpDigits("04-78 81x"))
    }

    @Test
    fun aCodeIsAtMostSixDigits() {
        assertEquals("047881", otpDigits("0478819"))
    }

    @Test
    fun anEmptiedFieldSubmitsNothing() {
        assertEquals("", otpDigits(""))
        assertEquals("", otpDigits("   "))
    }
}
