package com.chmaba.pos.ui.screens.inventory

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * How the inventory header counts and values a row.
 *
 * A product sold in variants keeps its units on the variants and leaves its own
 * balance at zero, so reading [InventoryItem.units] alone showed "0 units" and
 * valued the stock at nothing - the same gap the web overview had.
 */
class InventoryStockTest {

    private fun item(
        units: Int = 0,
        unitCost: Double? = null,
        variants: List<StockVariant> = emptyList(),
    ) = InventoryItem(
        productId = "p1",
        name = "MacBook",
        sku = "MB-1",
        units = units,
        reorderPoint = 10,
        color = Color.Unspecified,
        initials = "MB",
        unitCost = unitCost,
        variants = variants,
    )

    @Test
    fun aSimpleProductCountsAndValuesItsOwnUnits() {
        val simple = item(units = 3, unitCost = 5.0)
        assertEquals(3, simple.stockUnits)
        assertEquals(15.0, simple.stockValue!!, 0.001)
    }

    @Test
    fun aVariantProductSumsItsVariantsAtTheirOwnCost() {
        val variantProduct = item(
            unitCost = 800.0,
            variants = listOf(
                StockVariant("v1", "Space Gray 16/512", "MB-A", units = 1, reorderPoint = 10, unitCost = 700.0),
                StockVariant("v2", "Silver 32/512", "MB-B", units = 2, reorderPoint = 10, unitCost = 900.0),
            ),
        )
        assertEquals(3, variantProduct.stockUnits)
        assertEquals(700.0 + 2 * 900.0, variantProduct.stockValue!!, 0.001)
    }

    @Test
    fun aVariantWithoutItsOwnCostUsesTheProducts() {
        val variantProduct = item(
            unitCost = 50.0,
            variants = listOf(StockVariant("v1", "Only", "MB-A", units = 2, reorderPoint = 1)),
        )
        assertEquals(100.0, variantProduct.stockValue!!, 0.001)
    }

    @Test
    fun aUnitWithNoCostAnywhereIsUnpricedRatherThanFree() {
        val variantProduct = item(
            unitCost = null,
            variants = listOf(StockVariant("v1", "Only", "MB-A", units = 1, reorderPoint = 10)),
        )
        assertNull(variantProduct.stockValue)

        assertNull(item(units = 1, unitCost = null).stockValue)
    }

    @Test
    fun anEmptyVariantProductIsWorthNothingWithoutBeingUnpriced() {
        val empty = item(
            unitCost = null,
            variants = listOf(StockVariant("v1", "Only", "MB-A", units = 0, reorderPoint = 10)),
        )
        assertEquals(0, empty.stockUnits)
        assertEquals(0.0, empty.stockValue!!, 0.001)
    }
}
