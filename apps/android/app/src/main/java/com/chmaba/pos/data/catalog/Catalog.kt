package com.chmaba.pos.data.catalog

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
 * Product catalogue, mirroring the API's ProductRead
 * (chmabapos_api/app/schemas.py). `price` is a Decimal serialised as a string,
 * and stock lives in `on_hand`.
 */
data class CategoryDto(
    @SerializedName("name") val name: String? = null,
)

data class ProductDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("sku") val sku: String = "",
    @SerializedName("price") val price: String? = null,
    @SerializedName("on_hand") val onHand: Double = 0.0,
    @SerializedName("reorder_point") val reorderPoint: Int = 10,
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("image") val image: String? = null,
    @SerializedName("category") val category: CategoryDto? = null,
)

interface ProductsApi {
    @GET("products")
    suspend fun products(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("active_only") activeOnly: Boolean = true,
    ): List<ProductDto>
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
}
