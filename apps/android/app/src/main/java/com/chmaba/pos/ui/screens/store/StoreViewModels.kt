package com.chmaba.pos.ui.screens.store

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.catalog.CatalogRepository
import com.chmaba.pos.data.catalog.ProductDto
import com.chmaba.pos.data.store.CategoryCreateBody
import com.chmaba.pos.data.store.CategoryDto
import com.chmaba.pos.data.store.InventoryDto
import com.chmaba.pos.data.store.LoadState
import com.chmaba.pos.data.store.PurchaseDto
import com.chmaba.pos.data.store.StoreListRepository
import com.chmaba.pos.data.store.SupplierCreateBody
import com.chmaba.pos.data.store.SupplierDto
import com.chmaba.pos.data.store.money
import com.chmaba.pos.ui.screens.categories.Category
import com.chmaba.pos.ui.screens.inventory.InventoryItem
import com.chmaba.pos.ui.screens.products.Product
import com.chmaba.pos.ui.screens.products.ProductVariant
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
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load products")
            }
        }
    }

    /** True while a create or update is in flight, so the editor can disable Save. */
    var saving: Boolean by mutableStateOf(false)
        private set

    /** The last save failure; cleared when a save starts. */
    var saveError: String? by mutableStateOf(null)
        private set

    /**
     * Creates or updates a product and then reloads the catalogue, so the screen
     * shows what the server actually stored rather than what was typed.
     *
     * [existingId] null means create. [onSaved] runs only on success, so the
     * caller can close the editor; a failure leaves it open with [saveError] set.
     */
    fun save(
        existingId: String?,
        body: com.chmaba.pos.data.catalog.ProductWriteBody,
        onSaved: () -> Unit,
    ) {
        if (saving) return
        saving = true
        saveError = null
        viewModelScope.launch {
            try {
                if (existingId == null) repository.createProduct(body)
                else repository.updateProduct(existingId, body)
                state = LoadState.Ready(repository.products().map { it.toProduct() })
                saving = false
                onSaved()
            } catch (problem: Exception) {
                saving = false
                saveError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not save the product"
            }
        }
    }

    /** True while the variants are being saved, so the editor can hold its button. */
    var savingVariants: Boolean by mutableStateOf(false)
        private set

    /** The last variants failure, cleared when a new save starts. */
    var variantsError: String? by mutableStateOf(null)
        private set

    /**
     * Replaces a product's variants with [rows] and reloads, so the editor shows what
     * the server stored.
     *
     * The API treats the list as authoritative: a row left out is removed, and a row
     * that carries its id is updated rather than recreated.
     */
    fun saveVariants(productId: String, rows: List<ProductVariant>, onSaved: () -> Unit) {
        if (savingVariants) return
        savingVariants = true
        variantsError = null
        viewModelScope.launch {
            try {
                repository.setVariants(
                    productId,
                    com.chmaba.pos.data.catalog.VariantsSetBody(
                        rows.map { row ->
                            com.chmaba.pos.data.catalog.VariantWriteBody(
                                id = row.id,
                                name = row.name.trim(),
                                sku = row.sku.trim(),
                                price = row.price.trim().ifBlank { null },
                            )
                        },
                    ),
                )
                state = LoadState.Ready(repository.products().map { it.toProduct() })
                savingVariants = false
                onSaved()
            } catch (problem: Exception) {
                savingVariants = false
                variantsError = com.chmaba.pos.data.readableMessage(problem)
                    ?: "Could not save the variants"
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
        category = category?.name,
        price = money(price, com.chmaba.pos.data.orders.Session.currencyCode),
        stock = onHand.toInt(),
        reorderPoint = reorderPoint,
        color = colorFor(key),
        initials = initialsOf(name),
        isActive = isActive,
        costPrice = costPrice.orEmpty(),
        taxRate = taxRate.orEmpty(),
        barcode = barcode.orEmpty(),
        brand = brand.orEmpty(),
        description = description.orEmpty(),
        trackInventory = trackInventory,
        trackSerials = trackSerials,
        variants = variants.map { row ->
            ProductVariant(
                id = row.id,
                name = row.name,
                sku = row.sku,
                price = row.price.orEmpty(),
            )
        },
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
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load categories")
            }
        }
    }

    /** True while a write is in flight, so a dialog can hold its button. */
    var saving: Boolean by mutableStateOf(false)
        private set

    /** The last write failure, cleared when a new one starts. */
    var error: String? by mutableStateOf(null)
        private set

    fun clearError() {
        error = null
    }

    /** Adds a top-level category and reloads, so the list shows the server's name. */
    fun create(name: String, onCreated: () -> Unit) = write(
        "Could not add the category",
        onCreated,
    ) { repository.createCategory(CategoryCreateBody(name.trim())) }

    /** Renames one category and reloads. */
    fun rename(id: String, name: String, onRenamed: () -> Unit) = write(
        "Could not rename the category",
        onRenamed,
    ) { repository.renameCategory(id, name.trim()) }

    /**
     * Both writes behave the same way: block re-entry, clear the old error, call the
     * API, reload so the list shows the server's names, and report a failure without
     * closing the dialog.
     */
    private fun write(message: String, onDone: () -> Unit, call: suspend () -> Unit) {
        if (saving) return
        saving = true
        error = null
        viewModelScope.launch {
            try {
                call()
                state = LoadState.Ready(repository.categories().toCategories())
                saving = false
                onDone()
            } catch (problem: Exception) {
                saving = false
                error = com.chmaba.pos.data.readableMessage(problem) ?: message
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
            id = dto.id.orEmpty(),
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
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load inventory")
            }
        }
    }

    /** True while an inventory write is in flight, so the dialog can hold its button. */
    var saving: Boolean by mutableStateOf(false)
        private set

    /** The last inventory write failure, cleared when a new one starts. */
    var error: String? by mutableStateOf(null)
        private set

    fun clearError() {
        error = null
    }

    /** True while the catalogue CSV is being fetched, so Export can hold its button. */
    var exporting: Boolean by mutableStateOf(false)
        private set

    /** The last export failure, cleared when a new export starts. */
    var exportError: String? by mutableStateOf(null)
        private set

    fun clearExportError() {
        exportError = null
    }

    /**
     * Fetches the store's catalogue as CSV and hands the text to [onReady], which
     * writes it and opens the share sheet.
     *
     * The file is the API's own export rather than something rebuilt here, so its
     * columns cannot drift from the export the web app downloads.
     */
    fun export(onReady: (String) -> Unit) {
        if (exporting) return
        exporting = true
        exportError = null
        viewModelScope.launch {
            try {
                val csv = repository.productsCsv()
                exporting = false
                onReady(csv)
            } catch (problem: Exception) {
                exporting = false
                exportError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not export"
            }
        }
    }

    /**
     * Sets a product's on-hand outright and reloads.
     *
     * [onSaved] runs only on success, so the caller can close its dialog; a
     * failure leaves it open with [error] set.
     */
    fun adjust(productId: String, quantity: Int, onSaved: () -> Unit) =
        write("Could not adjust the stock", onSaved) { repository.adjustStock(productId, quantity) }

    /** Adds received stock, which the API takes as a positive delta rather than a total. */
    fun restock(productId: String, quantity: Int, onSaved: () -> Unit) =
        write("Could not receive the stock", onSaved) { repository.restockStock(productId, quantity) }

    /**
     * Both writes behave identically: block re-entry, clear the old error, call the
     * API, reload so the list shows the server's numbers rather than what was typed,
     * and report a failure without closing the dialog.
     */
    private fun write(message: String, onSaved: () -> Unit, call: suspend () -> Unit) {
        if (saving) return
        saving = true
        error = null
        viewModelScope.launch {
            try {
                call()
                state = LoadState.Ready(repository.inventory().map { it.toItem() })
                saving = false
                onSaved()
            } catch (problem: Exception) {
                saving = false
                error = com.chmaba.pos.data.readableMessage(problem) ?: message
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
        // Absent cost stays null rather than collapsing to 0, so the row is
        // excluded from valuation instead of understating it.
        unitCost = costPrice?.toDoubleOrNull(),
        trackSerials = trackSerials,
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
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load suppliers")
            }
        }
    }

    /** True while a create is in flight, so the form can hold its button. */
    var creating: Boolean by mutableStateOf(false)
        private set

    /**
     * The last create failure, cleared when a new attempt starts. A plan without
     * the `purchasing` feature answers 403 here.
     */
    var createError: String? by mutableStateOf(null)
        private set

    fun clearCreateError() {
        createError = null
    }

    /**
     * Creates a supplier and reloads, so the list shows what the server stored.
     *
     * [onCreated] runs only on success, which is what closes the form; a failure
     * leaves it open with [createError] set.
     */
    fun create(
        name: String,
        contactName: String?,
        phone: String?,
        email: String?,
        onCreated: () -> Unit,
    ) {
        if (creating) return
        creating = true
        createError = null
        viewModelScope.launch {
            try {
                repository.createSupplier(
                    SupplierCreateBody(
                        name = name.trim(),
                        contactName = contactName?.trim()?.takeIf { it.isNotBlank() },
                        phone = phone?.trim()?.takeIf { it.isNotBlank() },
                        email = email?.trim()?.takeIf { it.isNotBlank() },
                    ),
                )
                state = LoadState.Ready(repository.suppliers().map { it.toSupplier() })
                creating = false
                onCreated()
            } catch (problem: Exception) {
                creating = false
                createError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not add the supplier"
            }
        }
    }
}

private fun SupplierDto.toSupplier(): Supplier {
    val key = id ?: name
    return Supplier(
        name = name,
        // The payload's three contact fields, most specific first. A supplier
        // with none of them genuinely has no contact details recorded.
        contact = contactName?.takeIf { it.isNotBlank() }
            ?: phone?.takeIf { it.isNotBlank() }
            ?: email?.takeIf { it.isNotBlank() }
            ?: "No contact details",
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
                LoadState.Failed(com.chmaba.pos.data.readableMessage(problem) ?: "Could not load purchases")
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
