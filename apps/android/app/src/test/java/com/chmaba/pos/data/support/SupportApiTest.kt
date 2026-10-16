package com.chmaba.pos.data.support

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The help corpus's shape, pinned against a response the API actually sent.
 *
 * The API filters this payload per company and role before the app sees it, so nothing about who
 * may read what is testable here. What is: that a section carries its articles, and that an
 * article's numbered steps arrive as a list rather than as prose - the screen renders them as
 * numbers, so a change in shape would silently produce one unnumbered paragraph.
 */
class SupportApiTest {

    /** Truncated from a live `GET /support/articles`, 2026-10-15: the first section's first article. */
    private val response = """
        [{"id":"getting-started","title":"Getting started","blurb":"Set up your store and ring up your first sale.","articles":[{"id":"getting-started.first-sale","title":"Ring up your first sale","verticals":["coffee"],"roles":["owner","cashier"],"steps":["Open Point of sale from the sidebar.","Tap the products your customer is buying to add them to the cart."],"tip":"Open a shift before your first sale."},{"id":"getting-started.add-products","title":"Add your products","verticals":["coffee"],"roles":["owner"],"steps":["Go to Products."],"tip":null}]}]
    """.trimIndent()

    @Test
    fun aSectionCarriesItsArticlesAndTheirSteps() {
        val sections = Gson().fromJson(response, Array<SupportSectionDto>::class.java).toList()

        assertEquals(1, sections.size)
        assertEquals("Getting started", sections[0].title)
        assertEquals("Set up your store and ring up your first sale.", sections[0].blurb)
        assertEquals(2, sections[0].articles.size)

        val first = sections[0].articles[0]
        assertEquals("Ring up your first sale", first.title)
        assertEquals(2, first.steps.size)
        assertTrue(first.steps[1].startsWith("Tap the products"))
        assertEquals("Open a shift before your first sale.", first.tip)
    }

    @Test
    fun anArticleWithoutATipDoesNotInventOne() {
        val sections = Gson().fromJson(response, Array<SupportSectionDto>::class.java).toList()

        assertEquals(null, sections[0].articles[1].tip)
    }
}
