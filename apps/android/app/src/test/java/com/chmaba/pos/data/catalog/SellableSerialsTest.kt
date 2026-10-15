package com.chmaba.pos.data.catalog

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Which units a sale may name.
 *
 * The picker in the POS shows whatever this returns, and the API refuses the sale without
 * them, so the two rules that matter are pinned here: only units on the shelf, and only this
 * store's - or units belonging to no store.
 */
class SellableSerialsTest {

    private fun unit(serial: String, status: String = "in_stock", store: String? = null) =
        ProductSerialDto(id = serial, serialNumber = serial, storeId = store, status = status)

    @Test
    fun keepsThisStoresUnitsAndUnattributedOnes() {
        val rows = listOf(
            unit("a", store = "store-1"),
            unit("b"),
            unit("c", store = "store-2"),
        )

        assertEquals(listOf("a", "b"), sellableSerials(rows, "store-1").map { it.serialNumber })
    }

    @Test
    fun dropsUnitsThatAreNotOnTheShelf() {
        val rows = listOf(
            unit("a"),
            unit("b", status = "sold"),
            unit("c", status = "reserved"),
        )

        assertEquals(listOf("a"), sellableSerials(rows, "store-1").map { it.serialNumber })
    }

    @Test
    fun aWorkspaceWithNoStoreIdStillGetsTheUnattributedUnits() {
        val rows = listOf(unit("a", store = "store-1"), unit("b"))

        assertEquals(listOf("b"), sellableSerials(rows, null).map { it.serialNumber })
    }
}
