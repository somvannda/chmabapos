package com.chmaba.pos.data.auth

import com.chmaba.pos.data.orders.Session
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Keeps the refresh cookie across requests and restarts.
 *
 * The server renews the access token from an httpOnly `chmaba_refresh` cookie,
 * but the previous OkHttp setup configured no CookieJar, so every `Set-Cookie`
 * was discarded and the app could never renew anything.
 */
class PersistentCookieJar : CookieJar {

    private val byHost = mutableMapOf<String, MutableList<Cookie>>()

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        val list = byHost.getOrPut(url.host) { mutableListOf() }
        cookies.forEach { fresh ->
            // The server rotates the cookie, so the newest value must win.
            list.removeAll { it.name == fresh.name }
            list.add(fresh)
        }
        persist()
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        return byHost[url.host]?.filter { it.expiresAt > now }.orEmpty()
    }

    private fun persist() {
        val flat = byHost.entries
            .flatMap { (host, list) -> list.map { host to it } }
            .joinToString("\n") { (host, cookie) -> "$host\u0000$cookie" }
        SessionStore.saveCookies(flat)
    }

    /** Reloads after a restart. A malformed line is skipped rather than fatal. */
    @Synchronized
    fun restore() {
        val raw = SessionStore.cookies() ?: return
        raw.split("\n").forEach { line ->
            val parts = line.split("\u0000", limit = 2)
            if (parts.size != 2) return@forEach
            val url = HttpUrl.Builder().scheme("http").host(parts[0]).build()
            val cookie = Cookie.parse(url, parts[1]) ?: return@forEach
            byHost.getOrPut(parts[0]) { mutableListOf() }.add(cookie)
        }
    }
}

/**
 * Renews the access token shortly before it lapses.
 *
 * The token lives 60 minutes and nothing renewed it, so every screen began
 * failing with "Invalid access token" an hour into a shift.
 */
object SessionRefresh {

    private val mutex = Mutex()
    private val gson = Gson()

    /** Renew a little before the token actually lapses. */
    private const val SKEW_SECONDS = 120L

    /** The `exp` claim, or null when the token is not a readable JWT. */
    fun expiryEpochSeconds(token: String): Long? {
        val payload = token.split('.').getOrNull(1) ?: return null
        val json = decodeBase64Url(payload) ?: return null
        return Regex("\"exp\"\\s*:\\s*(\\d+)").find(json)?.groupValues?.get(1)?.toLongOrNull()
    }

    fun isExpiring(token: String, nowSeconds: Long = System.currentTimeMillis() / 1000): Boolean {
        val exp = expiryEpochSeconds(token) ?: return false
        return nowSeconds >= exp - SKEW_SECONDS
    }

    /**
     * Renews the token when it is close to expiry, otherwise does nothing.
     *
     * Serialised by [mutex] deliberately: the server rotates the refresh cookie,
     * so two concurrent refreshes would present the same pre-rotation cookie and
     * the second would be rejected. The web app guards the same hazard with a
     * single-flight coordinator (apps/web/src/lib/refreshCoordinator.js).
     *
     * A failed renewal leaves the current token alone; the request then fails
     * normally and the screen reports it, rather than silently signing out.
     */
    suspend fun ensureFresh(client: () -> OkHttpClient, baseUrl: String) = mutex.withLock {
        val before = Session.token ?: return@withLock
        if (!isExpiring(before)) return@withLock
        // Another caller may already have renewed while we waited for the lock.
        if (!isExpiring(Session.token ?: return@withLock)) return@withLock

        val fresh = withContext(Dispatchers.IO) {
            runCatching {
                val request = Request.Builder()
                    .url(baseUrl + "auth/refresh")
                    .post("".toRequestBody(null))
                    .build()
                client().newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@use null
                    val body = response.body?.string() ?: return@use null
                    gson.fromJson(body, TokenResponseDto::class.java)?.accessToken
                }
            }.getOrNull()
        }

        if (!fresh.isNullOrBlank()) {
            Session.token = fresh
            SessionStore.save(fresh, Session.userName, Session.userEmail)
        }
    }
}

/**
 * Decodes base64url without padding.
 *
 * Hand-rolled so the expiry logic is plain JVM code that a unit test can
 * exercise: `android.util.Base64` is not available off-device and
 * `java.util.Base64` is not available at the app's minSdk.
 */
private fun decodeBase64Url(value: String): String? {
    val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    val out = StringBuilder()
    var buffer = 0
    var bits = 0
    for (character in value) {
        val index = alphabet.indexOf(character)
        if (index < 0) return null
        buffer = (buffer shl 6) or index
        bits += 6
        if (bits >= 8) {
            bits -= 8
            out.append(((buffer shr bits) and 0xFF).toChar())
        }
    }
    return out.toString()
}
