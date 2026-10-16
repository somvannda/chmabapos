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
/**
 * The API's own words for a refusal, however the API shaped them.
 *
 * A refusal is a `detail` string: "Item is out of stock", "Your plan does not include purchasing".
 * A *validation* failure is a `detail` **list** of objects, each with a `msg` and a `loc`, and the
 * fallback used to hand the reader the raw JSON of one - a cashier at a till was shown
 * `{"detail":[{"type":"missing","loc":["body","items"],"msg":"Field required"...}]}`. A validation
 * failure is the kind a reader can act on, so the message and the field it names are worth digging
 * out. Null when the body says neither, so the caller can fall back to the raw body itself.
 */
fun apiDetailMessage(body: String): String? {
    Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.let { return it.groupValues[1] }

    val message = Regex("\"msg\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.get(1)
        ?: return null
    val field = Regex("\"loc\"\\s*:\\s*\\[([^\\]]*)\\]").find(body)?.groupValues?.get(1)
        ?.split(",")
        ?.map { it.trim().trim('"') }
        // "body" is the request itself, which tells the reader at a till nothing.
        ?.filter { it.isNotBlank() && it != "body" }
        ?.joinToString(".")
    return if (field.isNullOrBlank()) message else "$message ($field)"
}

fun readableMessage(problem: Throwable): String? {
    if (problem is HttpException) {
        val body = runCatching { problem.response()?.errorBody()?.string() }.getOrNull()
        if (!body.isNullOrBlank()) {
            // The API's own wording, whether it answered with a sentence or with a field it could
            // not find. The raw body is the last resort, not the answer for a validation failure.
            return apiDetailMessage(body) ?: body.take(200)
        }
    }
    // A request that never reached the server has no API explanation to unwrap, only
    // the socket's own words - "Failed to connect to localhost/127.0.0.1:5173" - which
    // says nothing a cashier can act on. Say what it means for the sale instead.
    if (problem is IOException) return "Could not reach the server. Check the connection and try again."
    return problem.message
}
