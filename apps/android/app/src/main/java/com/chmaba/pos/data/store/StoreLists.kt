package com.chmaba.pos.data.store

import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import okhttp3.ResponseBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

/**
 * Read-only endpoints for the remaining list screens, kept beside [StoreApi]
 * which owns orders and customers.
 *
 * Every DTO below was read from chmabapos_api, not inferred. Two consequences
 * worth knowing, both because the payloads are leaner than the prototype implied:
 *   - CategoryRead has **no product count**
 *   - the purchases list has **no total**, only `items`
 */

// ---------------------------------------------------------------- categories

/** Mirrors CategoryRead. */
data class CategoryDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("parent_id") val parentId: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("is_active") val isActive: Boolean = true,
)

/** Mirrors CategoryCreateRequest. Categories are company-scoped, so no store id. */
data class CategoryCreateBody(
    @SerializedName("name") val name: String,
    @SerializedName("parent_id") val parentId: String? = null,
)

/** Mirrors CategoryUpdateRequest; Gson omits nulls, so absent means leave alone. */
data class CategoryUpdateBody(
    @SerializedName("name") val name: String? = null,
    @SerializedName("is_active") val isActive: Boolean? = null,
)

// ---------------------------------------------------------------- inventory

/** One of a product's variants, as `InventoryRead` reports it under `variants`. */
data class InventoryVariantDto(
    @SerializedName("variant_id") val variantId: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("sku") val sku: String = "",
    @SerializedName("price") val price: String? = null,
    @SerializedName("cost_price") val costPrice: String? = null,
    @SerializedName("on_hand") val onHand: Double = 0.0,
    @SerializedName("reorder_point") val reorderPoint: Int = 0,
    @SerializedName("status") val status: String? = null,
)

/** Mirrors InventoryRead. `status` is supplied by the API: healthy | low | out. */
data class InventoryDto(
    @SerializedName("product_id") val productId: String? = null,
    @SerializedName("product_name") val productName: String = "",
    @SerializedName("sku") val sku: String = "",
    @SerializedName("price") val price: String? = null,
    /**
     * Catalog cost basis. Null when no cost is recorded, which is not the same
     * as zero — InventoryRead's own note says the UI must not value missing
     * cost as 0, so those rows are excluded from the stock figure instead.
     */
    @SerializedName("cost_price") val costPrice: String? = null,
    @SerializedName("on_hand") val onHand: Double = 0.0,
    @SerializedName("reorder_point") val reorderPoint: Int = 0,
    @SerializedName("status") val status: String? = null,
    @SerializedName("track_serials") val trackSerials: Boolean = false,
    /**
     * A product sold in variants carries its own balance *and* one per variant, and the two are
     * separate numbers. Reading these is what the screen used to skip, so a variant product showed
     * a figure the variants do not share and nothing said so.
     */
    @SerializedName("variants") val variants: List<InventoryVariantDto> = emptyList(),
)

// ---------------------------------------------------------------- suppliers
/**
 * Mirrors InventoryAdjustRequest. `quantity` is an absolute on-hand, not a delta.
 *
 * [variantId] names the variant whose balance is being set. Without it the API writes the
 * *product's* own balance - the handler branches on `payload.variant_id` - which for a product sold
 * in variants is a number no sale draws on, so a correction made there would look like it worked
 * and change nothing that matters.
 */
data class InventoryAdjustBody(
    @SerializedName("quantity") val quantity: Int,
    @SerializedName("reason") val reason: String = "manual_adjustment",
    @SerializedName("variant_id") val variantId: String? = null,
)

/**
 * Mirrors InventoryRestockRequest. Unlike [InventoryAdjustBody], `quantity` is a
 * positive delta — the number received — not a whole new on-hand total.
 *
 * [variantId] puts the units on the variant that was chosen. Without it the API writes the
 * *product's* own balance, which for a product sold in variants is a number no sale draws on.
 *
 * No `reason` is sent. The API names the movement from `reason` when it is given, otherwise from the
 * supplier, otherwise "Stock received", so leaving it out is what makes the stock history say where
 * the units came from. The app used to send a flat "received" and throw that away.
 *
 * [serialNumbers] is required by the API for a product that tracks serials - one per unit - and
 * refused for one that does not, which is why the form only asks when the product tracks them.
 */
data class InventoryRestockBody(
    @SerializedName("quantity") val quantity: Int,
    @SerializedName("variant_id") val variantId: String? = null,
    @SerializedName("supplier") val supplier: String? = null,
    @SerializedName("reference") val reference: String? = null,
    @SerializedName("unit_cost") val unitCost: String? = null,
    @SerializedName("serial_numbers") val serialNumbers: List<String>? = null,
)

/** Mirrors the dict shape returned by `GET /suppliers` (it has no response_model). */
data class SupplierDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("contact_name") val contactName: String? = null,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("is_active") val isActive: Boolean = true,
)

/** Mirrors what `POST /suppliers` accepts: a name plus optional contact fields. */
data class SupplierCreateBody(
    @SerializedName("name") val name: String,
    @SerializedName("contact_name") val contactName: String? = null,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
)

/**
 * Mirrors what `PATCH /suppliers/{id}` reads. That route takes a plain dict and replaces a field
 * only when the key is *present*, treating a blank as "clear it".
 *
 * So every field is sent every time, and the optional ones as empty strings rather than null. Gson
 * omits nulls, and an absent key means "leave it alone" - which would make clearing a phone number
 * silently do nothing while appearing to save.
 */
data class SupplierUpdateBody(
    @SerializedName("name") val name: String,
    @SerializedName("contact_name") val contactName: String = "",
    @SerializedName("phone") val phone: String = "",
    @SerializedName("email") val email: String = "",
)

// ---------------------------------------------------------------- purchases

/** Mirrors the dict shape returned by `GET /purchases`. */
data class PurchaseDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("po_number") val poNumber: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("supplier") val supplier: String? = null,
    @SerializedName("note") val note: String? = null,
    /** Raw line snapshot; only its length is used (the list has no total). */
    @SerializedName("items") val items: List<Any> = emptyList(),
    @SerializedName("created_at") val createdAt: String? = null,
)

/**
 * Mirrors what `POST /purchases` accepts. The handler reads this as a plain dict, so the shape
 * comes from v1.py:9237-9280 rather than a schema: one or more lines, optionally a supplier and a
 * note. `unit_cost` is what the store pays, not the selling price.
 */
data class PurchaseItemBody(
    @SerializedName("product_id") val productId: String,
    @SerializedName("quantity") val quantity: Int,
    @SerializedName("unit_cost") val unitCost: String? = null,
)

data class PurchaseCreateBody(
    @SerializedName("items") val items: List<PurchaseItemBody>,
    @SerializedName("supplier_id") val supplierId: String? = null,
    @SerializedName("note") val note: String? = null,
)

// ---------------------------------------------------------------- transport

interface StoreListApi {
    @GET("categories")
    suspend fun categories(@Header("Authorization") bearer: String): List<CategoryDto>

    /** Company-scoped, like the GET; no store header. */
    @POST("categories")
    suspend fun createCategory(
        @Header("Authorization") bearer: String,
        @Body body: CategoryCreateBody,
    ): CategoryDto

    /** Partial update: an omitted name leaves the existing one alone. */
    @PATCH("categories/{id}")
    suspend fun updateCategory(
        @Header("Authorization") bearer: String,
        @Path("id") id: String,
        @Body body: CategoryUpdateBody,
    ): CategoryDto

    /**
     * The catalogue as CSV, for the inventory screen's Export. The API answers with
     * text rather than JSON, so the body comes back raw for the caller to write to a
     * file. Like the other catalogue reads it is not plan-gated.
     */
    @Streaming
    @GET("products/export.csv")
    suspend fun exportProductsCsv(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
    ): ResponseBody

    @GET("inventory")
    suspend fun inventory(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("low_stock") lowStock: Boolean? = null,
    ): List<InventoryDto>

    /**
     * Sets on-hand outright. InventoryAdjustRequest takes an absolute quantity
     * rather than a delta, and has no approval gate.
     */
    @PATCH("inventory/{productId}")
    suspend fun adjustInventory(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("productId") productId: String,
        @Body body: InventoryAdjustBody,
    ): InventoryDto

    /**
     * Adds stock. `quantity` is a positive delta, unlike the adjust endpoint which
     * takes the new total; like adjust, it is not approval-gated.
     */
    @POST("inventory/{productId}/restock")
    suspend fun restockInventory(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("productId") productId: String,
        @Body body: InventoryRestockBody,
    ): InventoryDto

    @GET("suppliers")
    suspend fun suppliers(@Header("Authorization") bearer: String): List<SupplierDto>

    /**
     * Company-scoped, like the GET. The API requires the `purchasing` plan feature,
     * so a free plan answers 403 rather than creating anything.
     */
    @POST("suppliers")
    suspend fun createSupplier(
        @Header("Authorization") bearer: String,
        @Body body: SupplierCreateBody,
    ): SupplierDto

    /**
     * Replaces a supplier's details. Company-scoped like the rest, and gated on the same
     * `purchasing` feature, so a free plan answers 403 rather than changing anything.
     */
    @PATCH("suppliers/{supplierId}")
    suspend fun updateSupplier(
        @Header("Authorization") bearer: String,
        @Path("supplierId") supplierId: String,
        @Body body: SupplierUpdateBody,
    ): SupplierDto

    /**
     * The catalogue, for the purchase-order form's picker. Typed against the catalogue's own DTO
     * rather than a second copy of it.
     */
    @GET("products")
    suspend fun products(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("active_only") activeOnly: Boolean = true,
    ): List<com.chmaba.pos.data.catalog.ProductDto>

    /** Raises a purchase order. The API creates it "ordered" and refuses a body with no lines. */
    @POST("purchases")
    suspend fun createPurchase(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Body body: PurchaseCreateBody,
    ): PurchaseDto

    @GET("purchases")
    suspend fun purchases(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("limit") limit: Int = 50,
    ): List<PurchaseDto>

    /**
     * Receives an ordered purchase order: every line goes onto the shelf and the order closes.
     *
     * No body - the API reads the lines it stored. It answers 409 unless the order is still
     * "ordered", and 400 naming a serial-tracked product, which has to be received from Stock so
     * each unit gets a serial of its own.
     */
    @POST("purchases/{id}/receive")
    suspend fun receivePurchase(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
    ): PurchaseDto

    /**
     * Cancels an ordered purchase order: it stays on the list, marked Cancelled, and can no longer
     * be received.
     *
     * No body. The API answers 409 unless the order is still "ordered", and moves no stock - which
     * is what makes this the safe way out of an order raised by mistake.
     */
    @POST("purchases/{id}/cancel")
    suspend fun cancelPurchase(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
    ): PurchaseDto
}

object StoreListHttp {
    val api: StoreListApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(StoreListApi::class.java)
    }
}

class StoreListRepository(private val api: StoreListApi = StoreListHttp.api) {

    private fun bearer(): String =
        "Bearer " + (Session.token ?: throw IllegalStateException("Not signed in"))

    private fun store(): String =
        Session.storeId ?: throw IllegalStateException("No store selected for this account")

    suspend fun categories(): List<CategoryDto> = api.categories(bearer())

    suspend fun createCategory(body: CategoryCreateBody): CategoryDto =
        api.createCategory(bearer(), body)

    /** Renames in place; the API takes a partial update. */
    suspend fun renameCategory(id: String, name: String): CategoryDto =
        api.updateCategory(bearer(), id, CategoryUpdateBody(name = name))

    suspend fun inventory(lowStock: Boolean? = null): List<InventoryDto> =
        api.inventory(bearer(), store(), lowStock)

    /**
     * The API's own catalogue export, as text. Handing the reader the API's file means
     * the columns cannot drift from the export the web app downloads.
     */
    suspend fun productsCsv(): String = api.exportProductsCsv(bearer(), store()).string()

    /** Absolute set, not a delta; the API takes the new on-hand. */
    suspend fun adjustStock(productId: String, quantity: Int, variantId: String? = null): InventoryDto =
        api.adjustInventory(bearer(), store(), productId, InventoryAdjustBody(quantity, variantId = variantId))

    /**
     * A positive delta, not an absolute total. [body] names the variant the units belong to and
     * carries the receipt's own details, so it is passed through rather than unpacked here.
     */
    suspend fun restockStock(productId: String, body: InventoryRestockBody): InventoryDto =
        api.restockInventory(bearer(), store(), productId, body)

    suspend fun suppliers(): List<SupplierDto> = api.suppliers(bearer())

    /** Needs the `purchasing` plan feature; a free plan gets a 403 back. */
    suspend fun createSupplier(body: SupplierCreateBody): SupplierDto =
        api.createSupplier(bearer(), body)

    /** Needs the `purchasing` plan feature like the create, and a blank field clears it. */
    suspend fun updateSupplier(id: String, body: SupplierUpdateBody): SupplierDto =
        api.updateSupplier(bearer(), id, body)

    suspend fun purchases(): List<PurchaseDto> = api.purchases(bearer(), store())

    /** Receives an ordered purchase order. The stock moves on the server, not here. */
    suspend fun receivePurchase(id: String): PurchaseDto =
        api.receivePurchase(bearer(), store(), id)

    /** Cancels an ordered purchase order. Nothing moves; the order just stops being receivable. */
    suspend fun cancelPurchase(id: String): PurchaseDto =
        api.cancelPurchase(bearer(), store(), id)

    /** The catalogue, for the order form's picker. */
    suspend fun productsForOrder(): List<com.chmaba.pos.data.catalog.ProductDto> =
        api.products(bearer(), store())

    /** Raises a purchase order and answers with what the server recorded. */
    suspend fun createPurchase(body: PurchaseCreateBody): PurchaseDto =
        api.createPurchase(bearer(), store(), body)
}
