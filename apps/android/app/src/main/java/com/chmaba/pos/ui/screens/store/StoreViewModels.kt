package com.chmaba.pos.ui.screens.store

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.catalog.CatalogRepository
import com.chmaba.pos.data.catalog.ProductDto
import com.chmaba.pos.data.store.CategoryDto
import com.chmaba.pos.data.store.InventoryDto
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.data.store.PurchaseDto
import com.chmaba.pos.data.store.StoreListRepository
import com.chmaba.pos.data.store.SupplierDto
import com.chmaba.pos.data.store.money
import com.chmaba.pos.ui.screens.categories.Category
import com.chmaba.pos.ui.screens.inventory.InventoryItem
import com.chmaba.pos.ui.screens.products.Product
import com.chmaba.pos.ui.screens.purchasing.PurchaseOrder
import com.chmaba.pos.ui.screens.purchasing.PurchaseStatus
import com.chmaba.pos.ui.screens.suppliers.Supplier
import kotlinx.coroutines.launch

/**
 * One loader per remaining list screen. They all follow the shape proven on
 * Orders: expose [LoadState], map the API DTO to the screen's own model, and
 * never fabricate a field the payload does not carry.
 */

private val PALETTE = listOf(
    Color(0xFFD7C0A2), Color(0xFFB9D7A2), Color(0xFFB3B6D9), Color(0xFFF2C1A3),
    Color(0xFFF0C986), Color(0xFFC99E83), Color(0xFFA9C7BF), Color(0xFFE9AAB6),
)

private fun colorFor(key: String): Color = PALETTE[Math.abs(key.hashCode()) % PALETTE.size]

private fun initialsOf(name: String): String = name.split(" ")
    .mapNotNull { it.firstOrNull()?.uppercaseChar()?.toString() }
    .take(2)
    .joinToString("")
    .ifBlank { "?" }

private fun dateOf(iso: String?): String = (iso ?: "").substringBefore('T').ifBlank { "—" }

// ---------------------------------------------------------------- products

class ProductsViewModel(
    private val repository: CatalogRepository = CatalogRepository(),
) : ViewModel() {
    var state: LoadState<List<Product>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.products().map { it.toProduct() })
            } catch (problem: Exception) {
                LoadState.Failed(problem.message ?: "Could not load products")
            }
        }
    }
}

private fun ProductDto.toProduct(): Product {
    val key = id ?: "$sku$name"
    return Product(
        id = key,
        name = name,
        sku = sku,
        category = category?.name ?: "Uncategorised",
        price = money(price, "USD"),
        stock = onHand.toInt(),
        reorderPoint = reorderPoint,
        color = colorFor(key),
        initials = initialsOf(name),
        isActive = isActive,
    )
}

// ---------------------------------------------------------------- categories

class CategoriesViewModel(
    private val repository: StoreListRepository = StoreListRepository(),
) : ViewModel() {
    var state: LoadState<List<Category>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.categories().toCategories())
            } catch (problem: Exception) {
                LoadState.Failed(problem.message ?: "Could not load categories")
            }
        }
    }
}

/** Resolves parent names from the same list, since CategoryRead only carries ids. */
private fun List<CategoryDto>.toCategories(): List<Category> {
    val nameById = associate { (it.id ?: "") to it.name }
    return map { dto ->
        Category(
            name = dto.name,
            parent = dto.parentId?.let { nameById[it] },
            // CategoryRead has no product count, so the screen must not show one.
            productCount = 0,
            isActive = dto.isActive,
        )
    }
}

// ---------------------------------------------------------------- inventory

class InventoryViewModel(
    private val repository: StoreListRepository = StoreListRepository(),
) : ViewModel() {
    var state: LoadState<List<InventoryItem>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.inventory().map { it.toItem() })
            } catch (problem: Exception) {
                LoadState.Failed(problem.message ?: "Could not load inventory")
            }
        }
    }
}

private fun InventoryDto.toItem(): InventoryItem {
    val key = productId ?: sku
    return InventoryItem(
        productId = key,
        name = productName,
        sku = sku,
        units = onHand.toInt(),
        reorderPoint = reorderPoint,
        color = colorFor(key),
        initials = initialsOf(productName),
    )
}

// ---------------------------------------------------------------- suppliers

class SuppliersViewModel(
    private val repository: StoreListRepository = StoreListRepository(),
) : ViewModel() {
    var state: LoadState<List<Supplier>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.suppliers().map { it.toSupplier() })
            } catch (problem: Exception) {
                LoadState.Failed(problem.message ?: "Could not load suppliers")
            }
        }
    }
}

private fun SupplierDto.toSupplier(): Supplier {
    val key = id ?: name
    return Supplier(
        name = name,
        contact = contactName?.takeIf { it.isNotBlank() }
            ?: phone?.takeIf { it.isNotBlank() }
            ?: email?.takeIf { it.isNotBlank() }
            ?: "No contact",
        // Payment terms are not part of the suppliers payload.
        terms = "—",
        isActive = isActive,
        avatarColor = colorFor(key),
        initials = initialsOf(name),
    )
}

// ---------------------------------------------------------------- purchasing

class PurchasingViewModel(
    private val repository: StoreListRepository = StoreListRepository(),
) : ViewModel() {
    var state: LoadState<List<PurchaseOrder>> by mutableStateOf(LoadState.Loading)
        private set

    init { load() }

    fun load() {
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.purchases().map { it.toOrder() })
            } catch (problem: Exception) {
                LoadState.Failed(problem.message ?: "Could not load purchases")
            }
        }
    }
}

private fun PurchaseDto.toOrder(): PurchaseOrder = PurchaseOrder(
    reference = poNumber ?: "—",
    supplier = supplier ?: "—",
    // The payload has line snapshots but no total, so only the count is honest.
    lineCount = items.size,
    date = dateOf(createdAt),
    status = when (status?.lowercase()) {
        "open" -> PurchaseStatus.Open
        "partial" -> PurchaseStatus.Partial
        "received" -> PurchaseStatus.Received
        else -> PurchaseStatus.Draft
    },
    total = "—",
)
