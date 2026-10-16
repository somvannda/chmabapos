package com.chmaba.pos.data.team

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The shape of `GET /team`, pinned against a response the API actually sent.
 *
 * The payload is the only part of this screen a unit test can hold: the endpoint is
 * company-scoped, and the name and email the row shows live in a nested user object rather than at
 * the top level. Trimming a real response means a change to MembershipRead fails here instead of
 * the screen quietly rendering blanks.
 */
class TeamApiTest {

    /** Copied verbatim from a live `GET /team`, 2026-10-15. */
    private val response = """
        [{"id":"c38d321d-8889-4949-90d9-a9d917540ff9","user_id":"cdcb0fd4-0475-4b7b-a734-37ae7e782273","company_id":"c09c9600-896e-4ea8-919c-80179f0f4baf","role":"owner","status":"active","user":{"id":"cdcb0fd4-0475-4b7b-a734-37ae7e782273","email":"android-dev@example.com","full_name":"Android Dev","is_active":true,"is_email_verified":true,"platform_role":null,"preferences":null,"created_at":"2026-10-14T07:46:41.188000Z"},"store_ids":["093b805b-9a68-48c1-afb5-684c45161758"]}]
    """.trimIndent()

    @Test
    fun aMembershipCarriesThePersonItBelongsTo() {
        val members = Gson().fromJson(response, Array<MembershipDto>::class.java).toList()

        assertEquals(1, members.size)
        assertEquals("owner", members[0].role)
        assertEquals("active", members[0].status)
        assertEquals("android-dev@example.com", members[0].user?.email)
        assertEquals("Android Dev", members[0].user?.fullName)
        assertEquals(1, members[0].storeIds.size)
    }

    @Test
    fun aPayloadMissingTheNestedUserDoesNotThrow() {
        val members = Gson()
            .fromJson("""[{"id":"m1","role":"staff","status":"invited"}]""", Array<MembershipDto>::class.java)

        assertEquals("staff", members[0].role)
        assertEquals(null, members[0].user)
        assertEquals(0, members[0].storeIds.size)
    }
}
