package com.chmaba.pos.data.store

import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Query

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

// ---------------------------------------------------------------- inventory

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
)

// ---------------------------------------------------------------- suppliers

/** Mirrors the dict shape returned by `GET /suppliers` (it has no response_model). */
data class SupplierDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("contact_name") val contactName: String? = null,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("is_active") val isActive: Boolean = true,
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

// ---------------------------------------------------------------- transport

interface StoreListApi {
    @GET("categories")
    suspend fun categories(@Header("Authorization") bearer: String): List<CategoryDto>

    @GET("inventory")
    suspend fun inventory(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("low_stock") lowStock: Boolean? = null,
    ): List<InventoryDto>

    @GET("suppliers")
    suspend fun suppliers(@Header("Authorization") bearer: String): List<SupplierDto>

    @GET("purchases")
    suspend fun purchases(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("limit") limit: Int = 50,
    ): List<PurchaseDto>
}

object StoreListHttp {
    val api: StoreListApi by lazy {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(OkHttpClient.Builder().addInterceptor(logging).build())
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

    suspend fun inventory(lowStock: Boolean? = null): List<InventoryDto> =
        api.inventory(bearer(), store(), lowStock)

    suspend fun suppliers(): List<SupplierDto> = api.suppliers(bearer())

    suspend fun purchases(): List<PurchaseDto> = api.purchases(bearer(), store())
}
