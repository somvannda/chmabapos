package com.chmaba.pos.ui.screens.customers

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.store.CustomerDto
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
                LoadState.Failed(problem.message ?: "Could not load customers")
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
            ?: "No contact",
        // Only the detail payload carries these; the list shows points instead.
        orders = 0,
        spent = "—",
        points = points?.toDoubleOrNull()?.toInt() ?: 0,
        avatarColor = AVATAR_COLORS[Math.abs(key.hashCode()) % AVATAR_COLORS.size],
        initials = name.split(" ")
            .mapNotNull { it.firstOrNull()?.uppercaseChar()?.toString() }
            .take(2)
            .joinToString("")
            .ifBlank { "?" },
    )
}
