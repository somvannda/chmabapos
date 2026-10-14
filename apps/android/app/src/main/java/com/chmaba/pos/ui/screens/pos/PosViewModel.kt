package com.chmaba.pos.ui.screens.pos

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.catalog.CatalogRepository
import com.chmaba.pos.data.catalog.ProductDto
import com.chmaba.pos.data.orders.ModifierSelectionDto
import com.chmaba.pos.data.orders.OrderCreateDto
import com.chmaba.pos.data.orders.OrderItemDto
import com.chmaba.pos.data.orders.OrderTenderDto
import com.chmaba.pos.data.orders.OrdersRepository
import com.chmaba.pos.data.orders.Session
import kotlinx.coroutines.launch
import java.util.Locale
import java.util.UUID

/** Load state for the sellable catalogue. */
sealed interface ProductsState {
    data object Loading : ProductsState
    data class Error(val message: String) : ProductsState
    data class Ready(val products: List<PosProduct>) : ProductsState
}

/** A sale the server accepted. */
data class SaleOutcome(
    val orderNumber: String,
    val total: String,
)

/**
 * Owns the sellable catalogue and order submission.
 *
 * Products come from `GET /products`, so line ids are the server's UUIDs — the
 * value `POST /orders` requires. Nothing is persisted locally: if the submission
 * fails the cashier is told plainly and the cart is kept.
 */
class PosViewModel(
    private val orders: OrdersRepository = OrdersRepository(),
    private val catalog: CatalogRepository = CatalogRepository(),
) : ViewModel() {

    var productsState by mutableStateOf<ProductsState>(ProductsState.Loading)
        private set

    var submitting by mutableStateOf(false)
        private set

    var outcome by mutableStateOf<SaleOutcome?>(null)
        private set

    var error by mutableStateOf<String?>(null)
        private set

    init {
        loadProducts()
    }

    fun loadProducts() {
        productsState = ProductsState.Loading
        viewModelScope.launch {
            productsState = try {
                ProductsState.Ready(catalog.products().map { it.toPosProduct() })
            } catch (problem: Exception) {
                ProductsState.Error(problem.message ?: "Could not load products")
            }
        }
    }

    fun submit(
        lines: List<CartLine>,
        method: String,
        discount: Double,
        customer: String?,
        total: Double,
    ) {
        if (submitting) return
        submitting = true
        error = null
        viewModelScope.launch {
            try {
                val body = OrderCreateDto(
                    items = lines.map { line ->
                        OrderItemDto(
                            productId = line.product.id,
                            quantity = line.quantity,
                            modifiers = line.modifiers.map {
                                ModifierSelectionDto(it.name, amount(it.priceDelta))
                            },
                        )
                    },
                    paymentMethod = method,
                    tenders = listOf(OrderTenderDto(method, Session.currencyCode, amount(total))),
                    discount = amount(discount),
                    customerName = customer,
                    clientOrderId = UUID.randomUUID().toString(),
                )
                val order = orders.createOrder(body)
                outcome = SaleOutcome(
                    orderNumber = order.orderNumber ?: order.id?.take(8) ?: "—",
                    total = order.total ?: amount(total),
                )
            } catch (problem: Exception) {
                error = problem.message ?: "Could not send the order"
            } finally {
                submitting = false
            }
        }
    }

    fun clear() {
        outcome = null
        error = null
    }
}

private fun amount(value: Double): String = String.format(Locale.US, "%.2f", value)

/** Stable palette so a product keeps the same tile colour between visits. */
private val TILE_PALETTE = listOf(
    Color(0xFFD7C0A2), Color(0xFFB9D7A2), Color(0xFFF0C986), Color(0xFFF2C1A3),
    Color(0xFFB79A83), Color(0xFFC99E83), Color(0xFFB3B6D9), Color(0xFFD6A16F),
)

private fun ProductDto.toPosProduct(): PosProduct {
    val key = id ?: "$sku$name"
    return PosProduct(
        id = key,
        name = name,
        sku = sku,
        category = category?.name ?: "Uncategorised",
        price = price?.toDoubleOrNull() ?: 0.0,
        stock = onHand.toInt(),
        color = TILE_PALETTE[Math.abs(key.hashCode()) % TILE_PALETTE.size],
        initials = name.split(" ")
            .mapNotNull { it.firstOrNull()?.toString() }
            .take(2)
            .joinToString("")
            .uppercase(),
        // The API exposes modifier_group_id; groups are fetched separately.
        modifierGroups = emptyList(),
    )
}
