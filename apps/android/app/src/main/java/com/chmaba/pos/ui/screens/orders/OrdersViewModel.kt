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
                LoadState.Failed(problem.message ?: "Could not load orders")
            }
        }
    }
}

private fun OrderDto.toSummary(): OrderSummary {
    // The tender badge reflects how it was actually paid, which lives on the
    // tenders list (kind == "payment"); OrderRead has no single method field.
    val tender = tenders.firstOrNull { it.kind == "payment" } ?: tenders.firstOrNull()
    val method = when (tender?.method) {
        null -> "—"
        "cash" -> "Cash"
        "khqr" -> "KHQR"
        "trade_in" -> "Trade-in"
        else -> tender.method.replaceFirstChar { it.uppercaseChar() }
    }
    return OrderSummary(
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
