package com.chmaba.pos.ui.screens.store

import com.chmaba.pos.data.catalog.ProductDto
import com.chmaba.pos.data.catalog.ProductVariantDto
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * What the catalogue calls a product's stock.
 *
 * A product sold in variants keeps its units on the variants and leaves its own
 * balance at zero, so reading `on_hand` alone showed "0 units" for a product that
 * had units on the shelf.
 */
class ProductStockTest {

    @Test
    fun aSimpleProductCountsItsOwnBalance() {
        val product = ProductDto(
            id = "p1",
            name = "Coffee",
            sku = "COF",
            price = "3.00",
            onHand = 4.0,
        ).toProduct()
        assertEquals(4, product.stock)
    }

    @Test
    fun aVariantProductCountsItsVariants() {
        val product = ProductDto(
            id = "p2",
            name = "MacBook",
            sku = "MB",
            price = "930.00",
            onHand = 0.0,
            variants = listOf(
                ProductVariantDto(id = "v1", name = "16/512", sku = "MB-A", onHand = 1.0),
                ProductVariantDto(id = "v2", name = "32/512", sku = "MB-B", onHand = 2.0),
            ),
        ).toProduct()
        assertEquals(3, product.stock)
    }
}
