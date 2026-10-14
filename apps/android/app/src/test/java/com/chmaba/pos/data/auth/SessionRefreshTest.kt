package com.chmaba.pos.data.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The expiry logic is what decides whether the app renews before a request, so
 * it is tested directly. `isExpiring` takes the clock as a parameter for exactly
 * this reason.
 */
class SessionRefreshTest {

    private val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

    private fun base64Url(value: String): String {
        val bytes = value.toByteArray(Charsets.UTF_8)
        val out = StringBuilder()
        var buffer = 0
        var bits = 0
        for (byte in bytes) {
            buffer = (buffer shl 8) or (byte.toInt() and 0xFF)
            bits += 8
            while (bits >= 6) {
                bits -= 6
                out.append(alphabet[(buffer shr bits) and 0x3F])
            }
        }
        if (bits > 0) out.append(alphabet[(buffer shl (6 - bits)) and 0x3F])
        return out.toString()
    }

    private fun token(payloadJson: String) = "header.${base64Url(payloadJson)}.signature"

    @Test
    fun `reads exp from a real shaped payload`() {
        val jwt = token("""{"sub":"6f4a87ae","exp":1791976644,"sid":"55a4684d"}""")
        assertEquals(1_791_976_644L, SessionRefresh.expiryEpochSeconds(jwt))
    }

    @Test
    fun `renews only inside the skew window`() {
        val exp = 1_000_000L
        val jwt = token("""{"exp":$exp}""")
        // 121s before expiry: not yet.
        assertFalse(SessionRefresh.isExpiring(jwt, nowSeconds = exp - 121))
        // 119s before expiry: inside the 120s skew.
        assertTrue(SessionRefresh.isExpiring(jwt, nowSeconds = exp - 119))
        // Already past.
        assertTrue(SessionRefresh.isExpiring(jwt, nowSeconds = exp + 5))
    }

    @Test
    fun `an unreadable token never reports as expiring`() {
        // Never knowing the expiry must not turn into a refresh on every call.
        assertNull(SessionRefresh.expiryEpochSeconds("not-a-jwt"))
        assertNull(SessionRefresh.expiryEpochSeconds("header.!!!not-base64!!!.sig"))
        assertNull(SessionRefresh.expiryEpochSeconds("header.${base64Url("no exp claim")}.sig"))
        assertFalse(SessionRefresh.isExpiring("not-a-jwt", nowSeconds = 9_999_999_999L))
    }
}
