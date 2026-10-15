package com.chmaba.pos.data

import retrofit2.HttpException
import java.io.IOException

/**
 * The message worth showing a user for a failed request.
 *
 * Retrofit throws [HttpException], whose own `message` is only the status line —
 * "HTTP 403 Forbidden". The API's explanation lives in the error body as
 * `{"detail": "..."}`, which is where the useful part is: a plan limit, a
 * validation failure, "Paid orders require a refund flow".
 *
 * Without unwrapping it, every failure in the app reads as a bare status code.
 *
 * Falls back to the body (truncated) when `detail` is not a plain string — a 422
 * answers with a list — then to a plain line when the request never reached the
 * server at all, and finally to the exception's own message. Null when there is
 * nothing at all, so callers can supply their own wording.
 */
fun readableMessage(problem: Throwable): String? {
    if (problem is HttpException) {
        val body = runCatching { problem.response()?.errorBody()?.string() }.getOrNull()
        if (!body.isNullOrBlank()) {
            val detail = Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.get(1)
            return detail ?: body.take(200)
        }
    }
    // A request that never reached the server has no API explanation to unwrap, only
    // the socket's own words - "Failed to connect to localhost/127.0.0.1:5173" - which
    // says nothing a cashier can act on. Say what it means for the sale instead.
    if (problem is IOException) return "Could not reach the server. Check the connection and try again."
    return problem.message
}
