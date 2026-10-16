package com.chmaba.pos.data.orders

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.Response
import java.io.IOException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

/**
 * Which failures may be queued for a retry.
 *
 * This is the safety of the whole offline queue. A request that never reached the server can be tried
 * again; one the server answered was refused for a reason, and retrying it forever would be a till
 * that never stops resending a sale the API has already rejected. Queueing the wrong kind of failure
 * is worse than queueing nothing.
 */
class OfflineQueueTest {

    private fun http(code: Int) = HttpException(Response.error<Any>(code, "".toResponseBody()))

    @Test
    fun aNetworkFailureIsWorthRetrying() {
        assertTrue(shouldQueue(UnknownHostException("no route")))
        assertTrue(shouldQueue(SocketTimeoutException("timed out")))
        assertTrue(shouldQueue(IOException("connection reset")))
    }

    @Test
    fun aRefusalFromTheServerIsNot() {
        // The API was reached and said no. It will say no again.
        assertFalse(shouldQueue(http(400)))
        assertFalse(shouldQueue(http(403)))
        assertFalse(shouldQueue(http(422)))
    }

    @Test
    fun anythingElseIsLeftAlone() {
        // A bug in the app is not something to replay on the next launch.
        assertFalse(shouldQueue(IllegalStateException("not signed in")))
        assertFalse(shouldQueue(RuntimeException("unexpected")))
    }
}
