package com.chmaba.pos.data.store

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The body the supplier editor sends, pinned because the route it goes to is unusual.
 *
 * `PATCH /suppliers/{id}` takes a plain dict and replaces a field only when the key is *present*
 * (v1.py:9697). So an absent key means "leave it alone", and a blank means "clear it". Gson omits
 * nulls, which would make clearing a phone number silently do nothing while the form closed as if it
 * had saved - a failure nobody would see until they looked.
 */
class SupplierUpdateBodyTest {

    private val gson = Gson()

    @Test
    fun everyFieldIsPresentEvenWhenItIsBeingCleared() {
        val json = gson.toJson(SupplierUpdateBody(name = "Bean Traders"))
        assertEquals(
            """{"name":"Bean Traders","contact_name":"","phone":"","email":""}""",
            json,
        )
    }

    @Test
    fun theContactKeysAreNamedTheWayTheHandlerReadsThem() {
        // contact_name, not contactName: the handler reads the snake_case key and would ignore the
        // other, leaving the previous contact in place.
        val json = gson.toJson(
            SupplierUpdateBody(
                name = "Bean Traders",
                contactName = "Dara",
                phone = "+855 12 000 000",
                email = "dara@bean.example",
            ),
        )
        assertTrue(json.contains("\"contact_name\":\"Dara\""))
        assertTrue(json.contains("\"phone\":\"+855 12 000 000\""))
        assertTrue(json.contains("\"email\":\"dara@bean.example\""))
    }

    @Test
    fun theNameIsAlwaysSent() {
        // The handler ignores a blank name rather than clearing it, so the editor must send the real
        // one; a body without it would rename nothing.
        val json = gson.toJson(SupplierUpdateBody(name = "Bean Traders", phone = "1"))
        assertTrue(json.startsWith("{"))
        assertTrue(json.contains("\"name\":\"Bean Traders\""))
    }
}
