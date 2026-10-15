package com.chmaba.pos.data

import retrofit2.HttpException

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
 * answers with a list — and then to the exception's own message. Null when there
 * is nothing at all, so callers can supply their own wording.
 */
fun readableMessage(problem: Throwable): String? {
    if (problem is HttpException) {
        val body = runCatching { problem.response()?.errorBody()?.string() }.getOrNull()
        if (!body.isNullOrBlank()) {
            val detail = Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.get(1)
            return detail ?: body.take(200)
        }
    }
    return problem.message
}
