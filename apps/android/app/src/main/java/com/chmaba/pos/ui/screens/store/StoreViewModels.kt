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
import com.chmaba.pos.ui.screens.purchasing.purchaseBody
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
     * True once the variants are stored. The editor's save callback is empty, so without
     * this the screen gave no sign at all that the save had worked.
     */
    var variantsSaved: Boolean by mutableStateOf(false)
        private set

    fun clearVariantsSaved() {
        variantsSaved = false
    }

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
        variantsSaved = false
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
                variantsSaved = true
                onSaved()
            } catch (problem: Exception) {
                savingVariants = false
                variantsError = com.chmaba.pos.data.readableMessage(problem)
                    ?: "Could not save the variants"
            }
        }
    }

    /** True while a photo is uploading, and what came of it. */
    var uploading: Boolean by mutableStateOf(false)
        private set
    var uploadError: String? by mutableStateOf(null)
        private set

    /**
     * Sends [bytes] as the product's photo, then reloads so the list shows what the server holds.
     *
     * Reading the bytes needs a ContentResolver, so the screen does that and passes them in; this
     * method stays free of Android types it cannot be tested around.
     */
    fun uploadImage(
        productId: String,
        filename: String,
        mimeType: String,
        bytes: ByteArray,
        onDone: () -> Unit = {},
    ) {
        if (uploading) return
        uploading = true
        uploadError = null
        viewModelScope.launch {
            try {
                repository.uploadProductImage(
                    productId,
                    com.chmaba.pos.data.catalog.productImagePart(filename, mimeType, bytes),
                )
                state = LoadState.Ready(repository.products().map { it.toProduct() })
                uploading = false
                onDone()
            } catch (problem: Exception) {
                uploading = false
                uploadError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not upload the image"
            }
        }
    }

    /** True while serial numbers are being recorded, so the editor can hold its control. */
    var savingSerials: Boolean by mutableStateOf(false)
        private set

    /** How many units the last recording added, or null when none has succeeded yet. */
    var serialsAdded: Int? by mutableStateOf(null)
        private set

    /** The last failure while recording units, cleared when a new attempt starts. */
    var serialsError: String? by mutableStateOf(null)
        private set

    fun clearSerialsResult() {
        serialsAdded = null
        serialsError = null
    }

    /**
     * Records [numbers] as units of [productId] and reloads, so the stock figure the editor shows
     * is the one the server now holds.
     *
     * Each number is a physical unit: the API adds one to the store's balance for every number it
     * accepts (v1.py:3561). A unit that already exists is refused rather than counted twice.
     */
    fun addSerials(productId: String, numbers: List<String>, onAdded: () -> Unit) {
        if (savingSerials) return
        val cleaned = numbers.map { it.trim() }.filter { it.isNotEmpty() }
        if (cleaned.isEmpty()) return
        savingSerials = true
        serialsError = null
        serialsAdded = null
        viewModelScope.launch {
            try {
                repository.addSerials(productId, cleaned)
                state = LoadState.Ready(repository.products().map { it.toProduct() })
                savingSerials = false
                serialsAdded = cleaned.size
                onAdded()
            } catch (problem: Exception) {
                savingSerials = false
                serialsError = com.chmaba.pos.data.readableMessage(problem)
                    ?: "Could not add the serial numbers"
            }
        }
    }
}

internal fun ProductDto.toProduct(): Product {
    val key = id ?: "$sku$name"
    return Product(
        id = key,
        name = name,
        sku = sku,
        category = category?.name,
        price = money(price, com.chmaba.pos.data.orders.Session.currencyCode),
        rawPrice = price.orEmpty(),
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
        // A variant product's own balance is one number and each variant's is another; both are
        // shown, because either alone misleads.
        variants = variants.map {
            com.chmaba.pos.ui.screens.inventory.StockVariant(
                name = it.name,
                sku = it.sku,
                units = it.onHand.toInt(),
                reorderPoint = it.reorderPoint,
            )
        },
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
    /** The catalogue and the suppliers, for the order form. Loaded when it opens. */
    var formProducts: List<com.chmaba.pos.data.catalog.ProductDto> by mutableStateOf(emptyList())
        private set
    var formSuppliers: List<com.chmaba.pos.data.store.SupplierDto> by mutableStateOf(emptyList())
        private set

    /** True while an order is being raised, so the form can hold its button. */
    var creating: Boolean by mutableStateOf(false)
        private set

    /** The order number the server just made, or why it refused. */
    var createdReference: String? by mutableStateOf(null)
        private set
    var createError: String? by mutableStateOf(null)
        private set

    fun clearCreateResult() {
        createdReference = null
        createError = null
    }

    fun loadFormOptions() {
        viewModelScope.launch {
            try {
                formProducts = repository.productsForOrder()
            } catch (problem: Exception) {
                createError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not load the catalogue"
            }
            try {
                formSuppliers = repository.suppliers()
            } catch (problem: Exception) {
                // A supplier is optional on the server, so failing to list them is not fatal.
                formSuppliers = emptyList()
            }
        }
    }

    /**
     * Raises a purchase order for [lines], optionally from [supplierId].
     *
     * The form used to send a single line because it could only hold one; `PurchaseCreateBody.items`
     * has always taken a list. The API creates the order "ordered" and the stock only moves when it
     * is received, which is why the form says so. A product sold in variants is refused with a
     * message naming it, and that refusal is shown as it comes rather than pre-empted: only the
     * server knows which products those are.
     */
    fun raiseOrder(
        lines: List<com.chmaba.pos.ui.screens.purchasing.PoLine>,
        supplierId: String?,
        onRaised: () -> Unit,
    ) {
        if (creating) return
        val usable = lines.filter { it.productId.isNotBlank() && it.quantity > 0 }
        if (usable.isEmpty()) return
        creating = true
        createError = null
        createdReference = null
        viewModelScope.launch {
            try {
                // The body is built by the function the contract test pins (PurchaseBodyContractTest),
                // so a field the API refuses cannot come back without a test failing.
                val made = repository.createPurchase(purchaseBody(usable, supplierId))
                state = LoadState.Ready(repository.purchases().map { it.toOrder() })
                creating = false
                createdReference = made.poNumber ?: "—"
                onRaised()
            } catch (problem: Exception) {
                creating = false
                createError = com.chmaba.pos.data.readableMessage(problem) ?: "Could not raise the order"
            }
        }
    }

    /** The reference of the order being received, so its row can hold its button. */
    var receiving: String? by mutableStateOf(null)
        private set
    var receiveError: String? by mutableStateOf(null)
        private set

    fun clearReceiveResult() {
        receiveError = null
    }

    /** The reference of the order being cancelled, on the same terms. */
    var cancelling: String? by mutableStateOf(null)
        private set
    var cancelError: String? by mutableStateOf(null)
        private set

    fun clearCancelResult() {
        cancelError = null
    }

    /**
     * Cancels [orderId]: it stays on the list, marked Cancelled, and can no longer be received.
     *
     * The API refuses with 409 unless the order is still "ordered", which is why only such a row
     * offers this. It moves no stock, so it is the safe way out of an order raised by mistake -
     * unlike receiving, which cannot be undone from here.
     */
    fun cancel(orderId: String, reference: String, onCancelled: () -> Unit) {
        if (cancelling != null) return
        cancelling = reference
        cancelError = null
        viewModelScope.launch {
            try {
                repository.cancelPurchase(orderId)
                // Re-read rather than patch: the server decides what "cancelled" looks like.
                state = LoadState.Ready(repository.purchases().map { it.toOrder() })
                cancelling = null
                onCancelled()
            } catch (problem: Exception) {
                cancelling = null
                cancelError = com.chmaba.pos.data.readableMessage(problem)
                    ?: "Could not cancel the order"
            }
        }
    }

    /**
     * Receives [orderId]: every line goes onto the shelf and the order closes.
     *
     * It cannot be undone from here, which is why the screen asks first. The API refuses with 409
     * unless the order is still "ordered", and with 400 naming a serial-tracked product; that
     * refusal is shown as it comes, because only the server knows which products those are.
     */
    fun receive(orderId: String, reference: String, onReceived: () -> Unit) {
        if (receiving != null) return
        receiving = reference
        receiveError = null
        viewModelScope.launch {
            try {
                repository.receivePurchase(orderId)
                // The list is re-read rather than patched: the server decides what "received"
                // means, and the stock has already moved.
                state = LoadState.Ready(repository.purchases().map { it.toOrder() })
                receiving = null
                onReceived()
            } catch (problem: Exception) {
                receiving = null
                receiveError = com.chmaba.pos.data.readableMessage(problem)
                    ?: "Could not receive the order"
            }
        }
    }

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
    // The reference is what a person reads; the id is what the API takes to receive it.
    id = id.orEmpty(),
    reference = poNumber ?: "—",
    supplier = supplier ?: "—",
    // The payload has line snapshots but no total, so only the count is honest.
    lineCount = items.size,
    date = dateOf(createdAt),
    // The statuses the API actually writes: a purchase order is created "ordered", ends
    // "received", and can be "cancelled". "open" and "draft" are the prototype's - mapping
    // "ordered" into the fallback labelled every placed order as a draft and left the Open
    // tab permanently empty, which is what a live PO-000001 showed.
    status = when (status?.lowercase()) {
        "ordered", "open" -> PurchaseStatus.Open
        "partial" -> PurchaseStatus.Partial
        "received" -> PurchaseStatus.Received
        "cancelled" -> PurchaseStatus.Cancelled
        "draft" -> PurchaseStatus.Draft
        else -> PurchaseStatus.Draft
    },
    total = "—",
)
