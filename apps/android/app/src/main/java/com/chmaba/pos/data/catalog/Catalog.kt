package com.chmaba.pos.data.catalog

import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
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

/**
 * Product catalogue, mirroring the API's ProductRead
 * (chmabapos_api/app/schemas.py). `price` and the other money fields are
 * Decimals serialised as strings, and stock lives in `on_hand`.
 */
data class CategoryDto(
    @SerializedName("name") val name: String? = null,
)

data class ProductDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("sku") val sku: String = "",
    @SerializedName("price") val price: String? = null,
    @SerializedName("cost_price") val costPrice: String? = null,
    @SerializedName("tax_rate") val taxRate: String? = null,
    @SerializedName("barcode") val barcode: String? = null,
    @SerializedName("brand") val brand: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("unit") val unit: String = "each",
    @SerializedName("track_inventory") val trackInventory: Boolean = true,
    @SerializedName("track_serials") val trackSerials: Boolean = false,
    @SerializedName("category_id") val categoryId: String? = null,
    @SerializedName("on_hand") val onHand: Double = 0.0,
    @SerializedName("reorder_point") val reorderPoint: Int = 10,
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("image") val image: String? = null,
    @SerializedName("category") val category: CategoryDto? = null,
)

/**
 * Body for `POST /products` and `PATCH /products/{id}`, mirroring
 * ProductCreateRequest / ProductUpdateRequest. Gson omits null fields, which is
 * the PATCH semantic the API wants: an absent key means "leave this alone".
 *
 * `openingStock` and `reorderPoint` exist only on the create request, so the
 * editor leaves them null when updating.
 */
data class ProductWriteBody(
    @SerializedName("name") val name: String,
    @SerializedName("sku") val sku: String,
    @SerializedName("price") val price: String,
    @SerializedName("cost_price") val costPrice: String? = null,
    @SerializedName("tax_rate") val taxRate: String? = null,
    @SerializedName("category_id") val categoryId: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("barcode") val barcode: String? = null,
    @SerializedName("brand") val brand: String? = null,
    @SerializedName("track_inventory") val trackInventory: Boolean = true,
    @SerializedName("track_serials") val trackSerials: Boolean = false,
    @SerializedName("opening_stock") val openingStock: String? = null,
    @SerializedName("reorder_point") val reorderPoint: Int? = null,
)

interface ProductsApi {
    @GET("products")
    suspend fun products(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("active_only") activeOnly: Boolean = true,
    ): List<ProductDto>

    @POST("products")
    suspend fun createProduct(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Body body: ProductWriteBody,
    ): ProductDto

    @PATCH("products/{id}")
    suspend fun updateProduct(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
        @Body body: ProductWriteBody,
    ): ProductDto
}

object CatalogHttp {
    val api: ProductsApi by lazy {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(OkHttpClient.Builder().addInterceptor(logging).build())
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ProductsApi::class.java)
    }
}

class CatalogRepository(private val api: ProductsApi = CatalogHttp.api) {

    suspend fun products(): List<ProductDto> {
        val token = Session.token
            ?: throw IllegalStateException("Not signed in — showing no products")
        val storeId = Session.storeId
            ?: throw IllegalStateException("No store selected for this account")
        return api.products("Bearer $token", storeId)
    }

    suspend fun createProduct(body: ProductWriteBody): ProductDto {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.createProduct("Bearer $token", storeId, body)
    }

    suspend fun updateProduct(id: String, body: ProductWriteBody): ProductDto {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.updateProduct("Bearer $token", storeId, id, body)
    }
}
