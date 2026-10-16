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

    @Test
    fun aRefusalKeepsTheApisOwnSentence() {
        assertEquals("Item is out of stock", apiDetailMessage("""{"detail":"Item is out of stock"}"""))
    }

    @Test
    fun aValidationFailureNamesTheFieldRatherThanShowingJson() {
        // What the API actually answers for a body missing a field, seen at a till as raw JSON
        // before this: {"detail":[{"type":"missing","loc":["body","items"],"msg":"Field required"...
        val body = """{"detail":[{"type":"missing","loc":["body","items"],"msg":"Field required","input":{}}]}"""

        assertEquals("Field required (items)", apiDetailMessage(body))
    }

    @Test
    fun aValidationFailureWithNoFieldStillReadsAsASentence() {
        assertEquals("Field required", apiDetailMessage("""{"detail":[{"msg":"Field required"}]}"""))
    }

    @Test
    fun aBodyThatSaysNeitherIsLeftToTheCallerToShow() {
        // Then readableMessage falls back to the body itself, truncated.
        assertNull(apiDetailMessage("not json at all"))
        assertNull(apiDetailMessage("""{"error":"something else"}"""))
    }
}
