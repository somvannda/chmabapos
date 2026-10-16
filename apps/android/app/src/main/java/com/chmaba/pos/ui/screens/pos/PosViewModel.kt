package com.chmaba.pos.ui.screens.pos

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.catalog.CatalogRepository
import com.chmaba.pos.data.catalog.ModifierGroupDto
import com.chmaba.pos.data.catalog.ProductDto
import com.chmaba.pos.data.orders.ModifierSelectionDto
import com.chmaba.pos.data.orders.OfflineQueue
import com.chmaba.pos.data.orders.OrderCreateDto
import com.chmaba.pos.data.orders.OrderItemDto
import com.chmaba.pos.data.orders.OrderTenderDto
import com.chmaba.pos.data.orders.OrdersRepository
import com.chmaba.pos.data.orders.QueuedOrder
import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.orders.shouldQueue
import com.google.gson.Gson
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
 * value `POST /orders` requires.
 *
 * A sale the server refuses is reported plainly and the cart is kept. A sale the network could not
 * carry is *held* in the queue (data/orders/OfflineQueue.kt) and replayed later, which is what the
 * web POS does and what stops a dropped connection from charging nobody.
 */
class PosViewModel(
    private val orders: OrdersRepository = OrdersRepository(),
    private val catalog: CatalogRepository = CatalogRepository(),
) : ViewModel() {

    var productsState by mutableStateOf<ProductsState>(ProductsState.Loading)
        private set

    /** The sellable units per product id, for the serial picker. */
    var serialCandidates by
        mutableStateOf<Map<String, List<com.chmaba.pos.data.catalog.ProductSerialDto>>>(emptyMap())
        private set

    /** True while the picker's candidates are being fetched. */
    var loadingSerials by mutableStateOf(false)
        private set

    /** The last failure while fetching units, cleared when a new fetch starts. */
    var serialsError by mutableStateOf<String?>(null)
        private set

    /**
     * Fetches the units on the shelf for the products a sale has to name. Units attributed to
     * another store are dropped here, as the web POS does: only this store's units, or units
     * with no store at all, can leave this shelf.
     */
    fun loadSerials(productIds: List<String>) {
        val wanted = productIds.distinct().filter { it.isNotBlank() }
        if (wanted.isEmpty() || loadingSerials) return
        loadingSerials = true
        serialsError = null
        viewModelScope.launch {
            try {
                val store = Session.storeId
                val found = wanted.associateWith { id ->
                    // "On this shelf, and ours to sell": the rule lives in a pure function so
                    // it can be tested without a server (data/catalog/SellableSerials.kt).
                    com.chmaba.pos.data.catalog.sellableSerials(catalog.serials(id), store)
                }
                serialCandidates = serialCandidates + found
            } catch (problem: Exception) {
                serialsError = com.chmaba.pos.data.readableMessage(problem)
                    ?: "Could not load the units for this product"
            } finally {
                loadingSerials = false
            }
        }
    }

    var submitting by mutableStateOf(false)
        private set

    var outcome by mutableStateOf<SaleOutcome?>(null)
        private set

    var error by mutableStateOf<String?>(null)
        private set

    /**
     * True when the failure being shown was *kept* for a later send rather than lost. The error
     * sheet says something different in that case, because "nothing was charged" stops being true
     * the moment a held sale is replayed.
     */
    var waitingToSend by mutableStateOf(false)
        private set

    init {
        loadProducts()
    }

    fun loadProducts() {
        productsState = ProductsState.Loading
        viewModelScope.launch {
            productsState = try {
                // Modifier groups are company-scoped and fetched once; a failure
                // here must not stop the grid from loading, so it degrades to
                // products without options rather than an error screen.
                val groups = runCatching { catalog.modifierGroups() }
                    .getOrDefault(emptyList())
                    .associateBy { it.id.orEmpty() }
                ProductsState.Ready(catalog.products().map { it.toPosProduct(groups) })
            } catch (problem: Exception) {
                ProductsState.Error(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load products")
            }
        }
    }

    /**
     * The idempotency key for the sale being rung up, and the lines it was minted for.
     *
     * The API dedupes on `client_order_id`, so a retry of the *same* sale has to send the same
     * key - otherwise a sale that committed behind a timeout is recorded twice. A different
     * basket is a different sale, so the key is re-minted when the lines change. It is cleared
     * only on success, because [clear] is what the failure sheet's "Try again" calls and
     * dropping the key there would defeat the whole point of it.
     */
    private var attemptId: String? = null
    private var attemptLines: List<CartLine>? = null

    fun submit(
        lines: List<CartLine>,
        method: String,
        discount: Double,
        customer: String?,
        total: Double,
        /**
         * What the cashier actually took, for a cash sale. The API derives the change from the
         * tender, so recording [total] here claimed the customer handed over exactly the total:
         * a $20 note on a $4.95 sale was recorded as $4.95 tendered and no change. Floored at the
         * total, because the sheet will not let a sale complete for less.
         */
        received: Double = total,
        /**
         * The units chosen for each serial-tracked line, keyed by [CartLine.key]. Absent for
         * lines whose product does not track serials.
         */
        serials: Map<String, List<String>> = emptyMap(),
        /**
         * The application context, for the queue that holds a sale the network could not carry.
         * Passed in per call rather than kept: a view model outlives a screen and must not hold a
         * context. Only the application context is used, so nothing leaks either way.
         */
        context: Context,
    ) {
        if (submitting) return
        // Same basket, same key: a retry replays rather than creating a second sale.
        if (attemptId == null || attemptLines != lines) {
            attemptId = UUID.randomUUID().toString()
            attemptLines = lines
        }
        // This attempt's key, kept for the queue: a row is identified by the key, so a replay of
        // the same sale replaces the row rather than adding a second one.
        val key = attemptId.orEmpty()
        // Built before the attempt, so a failure can keep the very request that failed. Replaying
        // it is then the same sale, with the same client_order_id, rather than a new one.
        val body = OrderCreateDto(
            items = lines.map { line ->
                OrderItemDto(
                    productId = line.product.id,
                    quantity = line.quantity,
                    modifiers = line.modifiers.map {
                        ModifierSelectionDto(it.name, amount(it.priceDelta))
                    },
                    serialNumbers = serials[line.key]?.takeIf { it.isNotEmpty() },
                )
            },
            // The till records a tender, not a bare payment_method. The API refuses a
            // body carrying both (v1.py:5604-5605), which made every sale fail with
            // "The sale was not recorded"; and a tender is the richer record, because it
            // names the currency the cash was counted in. The web POS sends tenders alone.
            tenders = listOf(
                OrderTenderDto(method, Session.currencyCode, amount(maxOf(received, total))),
            ),
            discount = amount(discount),
            customerName = customer,
            clientOrderId = attemptId,
        )
        submitting = true
        error = null
        waitingToSend = false
        viewModelScope.launch {
            try {
                val order = orders.createOrder(body)
                outcome = SaleOutcome(
                    orderNumber = order.orderNumber ?: order.id?.take(8) ?: "—",
                    total = order.total ?: amount(total),
                )
                // The server has it, so nothing is waiting on it any more.
                OfflineQueue.remove(context, key)
                // Recorded, so the next sale gets its own key.
                attemptId = null
                attemptLines = null
            } catch (problem: Exception) {
                // A sale the network could not carry is kept and replayed later; one the server
                // refused is reported, because resending a refusal forever helps nobody.
                if (shouldQueue(problem)) {
                    OfflineQueue.add(
                        context,
                        QueuedOrder(
                            storeId = Session.storeId.orEmpty(),
                            clientOrderId = key,
                            bodyJson = Gson().toJson(body),
                            queuedAt = System.currentTimeMillis(),
                        ),
                    )
                    waitingToSend = true
                }
                error = com.chmaba.pos.data.readableMessage(problem) ?: "Could not send the order"
            } finally {
                submitting = false
            }
        }
    }

    fun clear() {
        outcome = null
        error = null
        waitingToSend = false
    }
}

private fun amount(value: Double): String = String.format(Locale.US, "%.2f", value)

/** Stable palette so a product keeps the same tile colour between visits. */
private val TILE_PALETTE = listOf(
    Color(0xFFD7C0A2), Color(0xFFB9D7A2), Color(0xFFF0C986), Color(0xFFF2C1A3),
    Color(0xFFB79A83), Color(0xFFC99E83), Color(0xFFB3B6D9), Color(0xFFD6A16F),
)

private fun ProductDto.toPosProduct(groups: Map<String, ModifierGroupDto>): PosProduct {
    val key = id ?: "$sku$name"
    // A product carries at most one group; the option list is what the ringing
    // sheet offers. min_select > 1 is not supported by the sheet, which picks a
    // single option per group, so only `required` is carried across.
    val group = modifierGroupId?.let { groups[it] }
    return PosProduct(
        id = key,
        name = name,
        sku = sku,
        barcode = barcode?.takeIf { it.isNotBlank() },
        trackSerials = trackSerials,
        category = category?.name ?: "Uncategorised",
        price = price?.toDoubleOrNull() ?: 0.0,
        stock = onHand.toInt(),
        color = TILE_PALETTE[Math.abs(key.hashCode()) % TILE_PALETTE.size],
        initials = name.split(" ")
            .mapNotNull { it.firstOrNull()?.toString() }
            .take(2)
            .joinToString("")
            .uppercase(),
        modifierGroups = group?.let {
            listOf(
                ModifierGroup(
                    name = it.name,
                    options = it.modifiers.map { option ->
                        ModifierOption(
                            id = option.id.orEmpty(),
                            name = option.name,
                            priceDelta = option.priceDelta?.toDoubleOrNull() ?: 0.0,
                        )
                    },
                    required = it.isRequired,
                    // The payload's own cap. Dropping it is what made a group single-choice.
                    maxSelect = it.maxSelect,
                ),
            )
        }.orEmpty(),
    )
}
