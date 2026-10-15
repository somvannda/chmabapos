package com.chmaba.pos.data.auth

import okhttp3.Cookie
import okhttp3.HttpUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The jar is process-wide and holds the refresh cookie, so save, load and clear
 * are worth pinning. The clear case is the one that matters: a refresh cookie
 * surviving sign-out is exactly the bug this covers.
 *
 * `SessionStore` is a no-op without an Android context, so none of this touches
 * Android APIs.
 */
class PersistentCookieJarTest {

    private val host = "localhost"

    private fun url() = HttpUrl.Builder()
        .scheme("http")
        .host(host)
        .port(5173)
        .addPathSegments("api/v1/auth/refresh")
        .build()

    private fun cookie(name: String, value: String, expiresInSeconds: Long = 3600) =
        Cookie.Builder()
            .name(name)
            .value(value)
            .hostOnlyDomain(host)
            .expiresAt(System.currentTimeMillis() + expiresInSeconds * 1000)
            .build()

    @Test
    fun `saves a cookie and serves it back for the same host`() {
        val jar = PersistentCookieJar()
        jar.saveFromResponse(url(), listOf(cookie("chmaba_refresh", "abc")))

        val loaded = jar.loadForRequest(url())
        assertEquals(1, loaded.size)
        assertEquals("abc", loaded.first().value)
    }

    @Test
    fun `keeps only the newest value when the server rotates a cookie`() {
        val jar = PersistentCookieJar()
        jar.saveFromResponse(url(), listOf(cookie("chmaba_refresh", "old")))
        jar.saveFromResponse(url(), listOf(cookie("chmaba_refresh", "new")))

        // Two entries for one name would let the server see a stale value.
        val loaded = jar.loadForRequest(url())
        assertEquals(1, loaded.size)
        assertEquals("new", loaded.first().value)
    }

    @Test
    fun `does not serve an expired cookie`() {
        val jar = PersistentCookieJar()
        jar.saveFromResponse(url(), listOf(cookie("chmaba_refresh", "gone", expiresInSeconds = -60)))

        assertTrue(jar.loadForRequest(url()).isEmpty())
    }

    @Test
    fun `clear leaves nothing behind, which is what sign-out relies on`() {
        val jar = PersistentCookieJar()
        jar.saveFromResponse(url(), listOf(cookie("chmaba_refresh", "abc")))

        jar.clear()

        assertTrue(jar.loadForRequest(url()).isEmpty())
    }
}
