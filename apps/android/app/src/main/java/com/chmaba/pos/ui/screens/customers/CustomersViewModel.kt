package com.chmaba.pos.ui.screens.customers

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.store.CustomerCreateBody
import com.chmaba.pos.data.store.CustomerDetailDto
import com.chmaba.pos.data.store.CustomerDto
import com.chmaba.pos.data.store.money
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.data.store.StoreRepository
import kotlinx.coroutines.launch

/**
 * Loads customers from `GET /customers`.
 *
 * Note what the list payload actually contains: `CustomerRead` has no order
 * count or lifetime spend — those live on `CustomerDetailRead` only. So the list
 * shows what is real (contact + loyalty points) rather than inventing figures.
 */
class CustomersViewModel(
    private val repository: StoreRepository = StoreRepository(),
) : ViewModel() {

    var state: LoadState<List<Customer>> by mutableStateOf(LoadState.Loading)
        private set

    init {
        load()
    }

    fun load(search: String? = null) {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.customers(search).map { it.toCustomer() })
            } catch (problem: Exception) {
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load customers")
            }
        }
    }

    /** True while a create is in flight, so the form can hold its button. */
    var creating: Boolean by mutableStateOf(false)
        private set

    /** The last create failure, cleared when a new attempt starts. */
    var createError: String? by mutableStateOf(null)
        private set

    fun clearCreateError() {
        createError = null
    }

    /**
     * Creates a customer and reloads, so the list shows what the server stored.
     *
     * [onCreated] runs only on success, so the caller can close its form; a failure
     * leaves it open with [createError] set.
     */
    fun create(name: String, phone: String?, email: String?, onCreated: () -> Unit) {
        if (creating) return
        creating = true
        createError = null
        viewModelScope.launch {
            try {
                repository.createCustomer(
                    CustomerCreateBody(
                        name = name.trim(),
                        phone = phone?.trim()?.takeIf { it.isNotBlank() },
                        email = email?.trim()?.takeIf { it.isNotBlank() },
                    ),
                )
                state = LoadState.Ready(repository.customers().map { it.toCustomer() })
                creating = false
                onCreated()
            } catch (problem: Exception) {
                creating = false
                createError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not add the customer"
            }
        }
    }
}

private val AVATAR_COLORS = listOf(
    Color(0xFFD7C0A2), Color(0xFFB9D7A2), Color(0xFFB3B6D9), Color(0xFFF2C1A3),
    Color(0xFFF0C986), Color(0xFFC99E83), Color(0xFFA9C7BF), Color(0xFFE9AAB6),
)

private fun CustomerDto.toCustomer(): Customer {
    val key = id ?: name
    return Customer(
        name = name,
        contact = phone?.takeIf { it.isNotBlank() }
            ?: email?.takeIf { it.isNotBlank() }
            ?: "No contact details",
        // Only the detail payload carries these; the list shows points instead.
        orders = 0,
        spent = "—",
        points = points?.toDoubleOrNull()?.toInt() ?: 0,
        avatarColor = AVATAR_COLORS[Math.abs(key.hashCode()) % AVATAR_COLORS.size],
        initials = initialsFor(name),
        id = id.orEmpty(),
        since = readableDate(createdAt),
    )
}

/**
 * Loads one customer from `GET /customers/{id}`. The list row only carries a
 * summary, so the detail is fetched when the row is opened rather than rebuilt
 * out of that row.
 */
class CustomerDetailViewModel(
    private val repository: StoreRepository = StoreRepository(),
) : ViewModel() {

    var state: LoadState<CustomerDetail> by mutableStateOf(LoadState.Loading)
        private set

    private var currentId: String? = null

    fun load(id: String) {
        currentId = id
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.customer(id).toDetail())
            } catch (problem: Exception) {
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load this customer")
            }
        }
    }

    /** Retry for the failure state; a no-op before the first [load]. */
    fun retry() {
        currentId?.let { load(it) }
    }
}

private fun CustomerDetailDto.toDetail(): CustomerDetail {
    val row = customer
    val key = row?.id ?: row?.name ?: "?"
    val name = row?.name ?: "Customer"
    return CustomerDetail(
        customer = Customer(
            name = name,
            contact = row?.phone?.takeIf { it.isNotBlank() }
                ?: row?.email?.takeIf { it.isNotBlank() }
                ?: "No contact details",
            // CustomerDetailRead is the only payload with these two.
            orders = ordersCount,
            spent = money(totalSpent, "USD"),
            points = row?.points?.toDoubleOrNull()?.toInt() ?: 0,
            avatarColor = AVATAR_COLORS[Math.abs(key.hashCode()) % AVATAR_COLORS.size],
            initials = initialsFor(name),
            id = row?.id.orEmpty(),
            since = readableDate(row?.createdAt),
        ),
        orders = orders.map { order ->
            CustomerOrder(
                number = order.orderNumber ?: "—",
                detail = "${order.items.sumOf { it.quantity }.toInt()} items · ${clockOf(order.createdAt)}",
                total = money(order.total, order.currencyCode ?: "USD"),
            )
        },
    )
}

private fun initialsFor(name: String): String = name.split(" ")
    .mapNotNull { it.firstOrNull()?.uppercaseChar()?.toString() }
    .take(2)
    .joinToString("")
    .ifBlank { "?" }

private val MONTHS = listOf(
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

/** "2024-03-12T09:00:00" -> "12 Mar 2024"; null when there is no date. */
private fun readableDate(iso: String?): String? {
    val date = iso?.substringBefore('T')?.takeIf { it.isNotBlank() } ?: return null
    val parts = date.split('-')
    if (parts.size != 3) return date
    val month = parts[1].toIntOrNull()?.let { MONTHS.getOrNull(it - 1) } ?: return date
    return "${parts[2].trimStart('0')} $month ${parts[0]}"
}

/** "2024-03-12T09:41:00" -> "09:41"; falls back to a dash. */
private fun clockOf(iso: String?): String {
    val time = iso?.substringAfter('T', "")?.take(5).orEmpty()
    return if (time.length == 5) time else "—"
}
