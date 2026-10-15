package com.chmaba.pos.data.store

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
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import java.util.Locale

/**
 * Shared load state for every screen that reads from the API, so loading and
 * failure are handled the same way everywhere instead of screen by screen.
 */
sealed interface LoadState<out T> {
    data object Loading : LoadState<Nothing>
    data class Failed(val message: String) : LoadState<Nothing>
    data class Ready<T>(val data: T) : LoadState<T>
}

/** "$1,234.50" — Locale.US so a comma-decimal locale cannot corrupt an amount. */
fun money(value: Double, currency: String = "USD"): String =
    if (currency == "KHR") {
        String.format(Locale.US, "%,.0f", value) + " KHR"
    } else {
        "$" + String.format(Locale.US, "%.2f", value)
    }

fun money(raw: String?, currency: String = "USD"): String =
    money(raw?.toDoubleOrNull() ?: 0.0, currency)

// ---------------------------------------------------------------- orders

/** Mirrors OrderRead (chmabapos_api/app/schemas.py). Decimals arrive as strings. */
data class OrderDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("order_number") val orderNumber: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("currency_code") val currencyCode: String? = null,
    @SerializedName("subtotal") val subtotal: String? = null,
    @SerializedName("discount") val discount: String? = null,
    @SerializedName("tax") val tax: String? = null,
    @SerializedName("total") val total: String? = null,
    @SerializedName("amount_paid") val amountPaid: String? = null,
    @SerializedName("balance_due") val balanceDue: String? = null,
    @SerializedName("order_type") val orderType: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("paid_at") val paidAt: String? = null,
    @SerializedName("items") val items: List<OrderItemDto> = emptyList(),
    @SerializedName("tenders") val tenders: List<OrderTenderDto> = emptyList(),
)

/**
 * Mirrors OrderItemRead.
 *
 * `modifiers` is `list[dict[str, Any]]` server-side — an untyped list — so it is
 * deliberately not mapped here rather than guessing at its keys. The line note
 * therefore shows the variant only.
 */
data class OrderItemDto(
    @SerializedName("product_name") val productName: String = "",
    @SerializedName("sku") val sku: String = "",
    @SerializedName("variant_name") val variantName: String? = null,
    @SerializedName("unit_price") val unitPrice: String? = null,
    @SerializedName("quantity") val quantity: Double = 0.0,
    @SerializedName("line_total") val lineTotal: String? = null,
)

/** Mirrors OrderTenderRead. `kind` is "payment" or "change". */
data class OrderTenderDto(
    @SerializedName("kind") val kind: String? = null,
    @SerializedName("method") val method: String? = null,
    @SerializedName("currency_code") val currencyCode: String? = null,
    @SerializedName("amount") val amount: String? = null,
)

// ---------------------------------------------------------------- customers

/** Mirrors CustomerRead. */
data class CustomerDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("notes") val notes: String? = null,
    @SerializedName("points") val points: String? = null,
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("created_at") val createdAt: String? = null,
)

/** Mirrors CustomerCreateRequest. Customers are company-scoped, so no store id. */
data class CustomerCreateBody(
    @SerializedName("name") val name: String,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("notes") val notes: String? = null,
)

/** Mirrors CustomerDetailRead. */
data class CustomerDetailDto(
    @SerializedName("customer") val customer: CustomerDto? = null,
    @SerializedName("orders_count") val ordersCount: Int = 0,
    @SerializedName("total_spent") val totalSpent: String? = null,
    @SerializedName("orders") val orders: List<OrderDto> = emptyList(),
)

// ---------------------------------------------------------------- transport

interface StoreApi {
    @GET("orders")
    suspend fun orders(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("limit") limit: Int = 50,
    ): List<OrderDto>

    @GET("orders/{id}")
    suspend fun order(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
    ): OrderDto

    @GET("customers")
    suspend fun customers(
        @Header("Authorization") bearer: String,
        @Query("search") search: String? = null,
    ): List<CustomerDto>

    @GET("customers/{id}")
    suspend fun customer(
        @Header("Authorization") bearer: String,
        @Path("id") id: String,
    ): CustomerDetailDto

    /** Company-scoped: like the GET, it takes no X-Store-ID. */
    @POST("customers")
    suspend fun createCustomer(
        @Header("Authorization") bearer: String,
        @Body body: CustomerCreateBody,
    ): CustomerDto
}

object StoreHttp {
    val api: StoreApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(StoreApi::class.java)
    }
}

class StoreRepository(private val api: StoreApi = StoreHttp.api) {

    private fun bearer(): String =
        "Bearer " + (Session.token ?: throw IllegalStateException("Not signed in"))

    private fun store(): String =
        Session.storeId ?: throw IllegalStateException("No store selected for this account")

    suspend fun orders(limit: Int = 50): List<OrderDto> = api.orders(bearer(), store(), limit)

    suspend fun order(id: String): OrderDto = api.order(bearer(), store(), id)

    suspend fun customers(search: String? = null): List<CustomerDto> = api.customers(bearer(), search)

    suspend fun customer(id: String): CustomerDetailDto = api.customer(bearer(), id)

    suspend fun createCustomer(body: CustomerCreateBody): CustomerDto = api.createCustomer(bearer(), body)
}
