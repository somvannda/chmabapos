package com.chmaba.pos.ui.screens.orders

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.data.store.OrderDto
import com.chmaba.pos.data.store.StoreRepository
import com.chmaba.pos.data.store.money
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.OrderStatus
import kotlinx.coroutines.launch

/**
 * Loads the store's orders from `GET /orders`.
 *
 * The API's order `status` values are: paid, payment_pending, pending_pickup,
 * payment_failed, payment_expired, reservation_expired, cancelled, refunded.
 */
class OrdersViewModel(
    private val repository: StoreRepository = StoreRepository(),
) : ViewModel() {

    var state: LoadState<List<OrderSummary>> by mutableStateOf(LoadState.Loading)
        private set

    init {
        load()
    }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.orders().map { it.toSummary() })
            } catch (problem: Exception) {
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load orders")
            }
        }
    }
}

/**
 * Loads one order from `GET /orders/{id}` for the detail screen. The list only
 * carries a summary, so the detail is fetched separately rather than reusing a
 * row.
 */
class OrderDetailViewModel(
    private val repository: StoreRepository = StoreRepository(),
) : ViewModel() {

    var state: LoadState<OrderDetail> by mutableStateOf(LoadState.Loading)
        private set

    private var currentId: String? = null

    fun load(id: String) {
        currentId = id
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.order(id).toDetail())
            } catch (problem: Exception) {
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load this order")
            }
        }
    }

    /** Retry for the failure state; a no-op before the first [load]. */
    fun retry() {
        currentId?.let { load(it) }
    }

    /** True while a cancel is in flight, so the confirm dialog can hold its button. */
    var cancelling: Boolean by mutableStateOf(false)
        private set

    /** The last cancel refusal, cleared when a new attempt starts. */
    var cancelError: String? by mutableStateOf(null)
        private set

    fun clearCancelError() {
        cancelError = null
    }

    /**
     * Cancels the order and reloads it, so the screen shows its new status.
     *
     * A paid order is refused unless the store's approval policy allows it, and a
     * policy set to ask answers with a pending approval instead. Both are reported
     * as outcomes rather than treated as a failure of the app, because on a default
     * policy a paid order legitimately cannot be cancelled.
     */
    fun cancel(onDone: () -> Unit) {
        val id = currentId ?: return
        if (cancelling) return
        cancelling = true
        cancelError = null
        viewModelScope.launch {
            try {
                when (val outcome = repository.cancelOrder(id)) {
                    is com.chmaba.pos.data.store.CancelOutcome.Cancelled -> {
                        state = LoadState.Ready(repository.order(id).toDetail())
                        cancelling = false
                        onDone()
                    }

                    is com.chmaba.pos.data.store.CancelOutcome.PendingApproval -> {
                        cancelling = false
                        cancelError = "Sent for approval. Cancelling a paid order needs a manager's approval."
                    }

                    is com.chmaba.pos.data.store.CancelOutcome.Refused -> {
                        cancelling = false
                        cancelError = outcome.message
                    }
                }
            } catch (problem: Exception) {
                cancelling = false
                cancelError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not cancel the order"
            }
        }
    }
}

private fun OrderDto.toSummary(): OrderSummary {
    // The tender badge reflects how it was actually paid, which lives on the
    // tenders list (kind == "payment"); OrderRead has no single method field.
    val method = methodLabel(tenders.firstOrNull { it.kind == "payment" }?.method)
    return OrderSummary(
        // The detail endpoint needs the UUID, so the list row keeps it.
        id = id.orEmpty(),
        number = orderNumber ?: "—",
        customer = customerName?.takeIf { it.isNotBlank() } ?: "Walk-in",
        time = clockOf(createdAt),
        method = method,
        methodTone = when (method) {
            "KHQR" -> BadgeTone.Violet
            "Cash" -> BadgeTone.Green
            else -> BadgeTone.Neutral
        },
        status = statusOf(status),
        total = money(total, currencyCode ?: "USD"),
    )
}

private fun OrderDto.toDetail(): OrderDetail {
    val currency = currencyCode ?: "USD"
    val tender = tenders.firstOrNull { it.kind == "payment" } ?: tenders.firstOrNull()
    // Only a real change tender is shown; the sample's "Bakong ref" has no
    // counterpart in OrderRead, so it is gone rather than faked.
    val change = tenders.firstOrNull { it.kind == "change" }
    return OrderDetail(
        number = orderNumber ?: "—",
        meta = listOf(
            customerName?.takeIf { it.isNotBlank() } ?: "Walk-in",
            stampOf(createdAt),
        ).joinToString(" · "),
        status = statusOf(status),
        lines = items.map { item ->
            OrderLine(
                name = "${item.productName} × ${unitsLabel(item.quantity)}",
                note = item.variantName?.takeIf { it.isNotBlank() },
                amount = money(item.lineTotal, currency),
            )
        },
        subtotal = money(subtotal, currency),
        discount = discount
            ?.toDoubleOrNull()
            ?.takeIf { it > 0.0 }
            ?.let { money(discount, currency) },
        tax = money(tax, currency),
        total = money(total, currency),
        method = methodLabel(tender?.method),
        paid = money(amountPaid, currency),
        change = change?.let { money(it.amount, currency) },
    )
}

/** Shared by the list and the detail so both label a tender the same way. */
private fun methodLabel(raw: String?): String = when (raw) {
    null -> "—"
    "cash" -> "Cash"
    "khqr" -> "KHQR"
    "trade_in" -> "Trade-in"
    else -> raw.replaceFirstChar { it.uppercaseChar() }
}

private fun statusOf(raw: String?): OrderStatus = when (raw) {
    "paid" -> OrderStatus.Paid
    "payment_pending" -> OrderStatus.Pending
    "pending_pickup" -> OrderStatus.Pickup
    "refunded" -> OrderStatus.Refunded
    "cancelled" -> OrderStatus.Cancelled
    // payment_failed / payment_expired / reservation_expired are the failure
    // family. Anything unrecognised also lands here rather than being shown as
    // "Paid", which would overstate what happened.
    else -> OrderStatus.Failed
}

/** "2026-10-14T10:42:11+07:00" -> "10:42"; falls back to a dash. */
private fun clockOf(iso: String?): String {
    val time = iso?.substringAfter('T', "")?.take(5).orEmpty()
    return if (time.length == 5) time else "—"
}

private val MONTHS = listOf(
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

/** "2026-10-14T10:42:11+07:00" -> "14 Oct, 10:42"; falls back to the raw date. */
private fun stampOf(iso: String?): String {
    val date = iso?.substringBefore('T').orEmpty()
    val time = iso?.substringAfter('T', "")?.take(5).orEmpty()
    val parts = date.split('-')
    if (parts.size != 3 || time.length != 5) return date.ifBlank { "—" }
    val month = parts[1].toIntOrNull()?.let { MONTHS.getOrNull(it - 1) } ?: return date
    return "${parts[2].trimStart('0')} $month, $time"
}

/** Quantities are floats server-side; 2.0 reads as "2", 1.5 stays "1.5". */
private fun unitsLabel(value: Double): String =
    if (value % 1.0 == 0.0) value.toInt().toString() else "%.1f".format(value)
