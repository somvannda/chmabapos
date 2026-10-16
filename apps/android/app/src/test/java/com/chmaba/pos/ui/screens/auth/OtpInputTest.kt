package com.chmaba.pos.ui.screens.auth

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The rule behind the six-box verification code (issue #744).
 *
 * The bug this pins: each box kept only the first character of what arrived, so a pasted code lost
 * everything after its first digit - and one code in ten begins with 0, which is precisely the
 * digit that then went missing. Reached by walking the app's own sign-up flow, which had only ever
 * been exercised down its 409 path.
 */
class OtpInputTest {

    @Test
    fun aPastedCodeIsKeptWhole() {
        assertEquals("060534", otpAfterInput("", 0, "060534"))
    }

    @Test
    fun aLeadingZeroSurvivesArrivingOneDigitAtATime() {
        var value = ""
        "060534".forEachIndexed { index, digit -> value = otpAfterInput(value, index, digit.toString()) }

        assertEquals("060534", value)
    }

    @Test
    fun aDigitReplacesWhateverItsBoxHeld() {
        // Correcting the second digit of a code already entered.
        assertEquals("090534", otpAfterInput("060534", 1, "9"))
    }

    @Test
    fun clearingABoxLeavesItEmptyRatherThanStale() {
        // Box one emptied: the rest keep their places, so the field reads as a space then "60534".
        // The screen drops non-digits before submitting, which is what makes the gap harmless.
        assertEquals(" 60534", otpAfterInput("060534", 0, ""))
        assertEquals("06 534", otpAfterInput("060534", 2, ""))
    }

    @Test
    fun nothingArrivesFromAKeyThatIsNotADigit() {
        assertEquals("06", otpAfterInput("06", 2, "x"))
    }
}
