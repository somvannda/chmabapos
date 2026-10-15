package com.chmaba.pos.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.net.ConnectException
import java.net.SocketTimeoutException

/**
 * The message a failed request shows the reader.
 *
 * A request that never reached the API carries no explanation to unwrap, only the
 * socket's own words, which name a host and a port. Whoever sees that screen is
 * standing at a till, so the text has to become something they can act on.
 */
class ApiErrorsTest {

    @Test
    fun aConnectionFailureBecomesPlainWords() {
        val socketText = ConnectException("Failed to connect to localhost/127.0.0.1:5173")
        assertEquals(
            "Could not reach the server. Check the connection and try again.",
            readableMessage(socketText),
        )
    }

    @Test
    fun aTimeoutIsTreatedTheSameWay() {
        // A timeout is an IOException too, and the reader needs the same advice.
        assertEquals(
            "Could not reach the server. Check the connection and try again.",
            readableMessage(SocketTimeoutException("timeout")),
        )
    }

    @Test
    fun otherFailuresKeepTheirOwnMessage() {
        // Everything that is not a transport failure is left alone: the callers depend
        // on the API's own wording reaching the screen.
        assertEquals("boom", readableMessage(IllegalStateException("boom")))
        assertNull(readableMessage(IllegalStateException()))
    }
}
