package com.chmaba.pos.ui.screens.store

import com.chmaba.pos.data.catalog.ProductDto
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * What the product editor inherits from the catalogue.
 *
 * The editor seeds its own price field from [Product.rawPrice], because [Product.price] carries
 * the store's currency sign and no prefix-stripping can keep up with that - a hardcoded "$" was
 * there until money() learned baht and riel, and the editor would then have saved "฿12.00" as a
 * price. This pins both halves: the display formatted, the editable one raw.
 */
class ProductPriceTest {

    @Test
    fun theDisplayPriceIsSignedAndTheEditableOneIsNot() {
        val product = ProductDto(id = "p1", name = "Latte", sku = "COF-1", price = "4.50").toProduct()

        assertEquals("4.50", product.rawPrice)
        assertEquals("$4.50", product.price)
    }

    @Test
    fun aProductWithNoPriceIsEmptyInBoth() {
        val product = ProductDto(id = "p2", name = "Freebie", sku = "FREE-1").toProduct()

        assertEquals("", product.rawPrice)
        assertEquals("$0.00", product.price)
    }
}
