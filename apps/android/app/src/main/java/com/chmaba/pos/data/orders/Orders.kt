package com.chmaba.pos.data.orders

import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST

/**
 * Order submission, mirroring the API's create-order contract
 * (chmabapos_api/app/schemas.py: OrderCreateRequest / OrderItemRequest /
 * OrderTenderRequest). Decimals travel as strings so no float rounding is
 * introduced on the wire, which is what the web client does too.
 */
data class ModifierSelectionDto(
    @SerializedName("name") val name: String,
    @SerializedName("price_delta") val priceDelta: String,
)

data class OrderItemDto(
    @SerializedName("product_id") val productId: String?,
    @SerializedName("quantity") val quantity: Int,
    @SerializedName("modifiers") val modifiers: List<ModifierSelectionDto> = emptyList(),
)

data class OrderTenderDto(
    @SerializedName("method") val method: String,
    @SerializedName("currency_code") val currencyCode: String,
    @SerializedName("amount") val amount: String,
)

data class OrderCreateDto(
    @SerializedName("items") val items: List<OrderItemDto>,
    @SerializedName("payment_method") val paymentMethod: String? = null,
    @SerializedName("tenders") val tenders: List<OrderTenderDto>? = null,
    @SerializedName("discount") val discount: String = "0.00",
    @SerializedName("customer_name") val customerName: String? = null,
    /** Idempotency key: a replay of the same sale returns the existing order. */
    @SerializedName("client_order_id") val clientOrderId: String? = null,
    @SerializedName("order_type") val orderType: String = "takeaway",
)

data class OrderReadDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("order_number") val orderNumber: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("total") val total: String? = null,
)

interface OrdersApi {
    @POST("orders")
    suspend fun createOrder(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Body body: OrderCreateDto,
    ): OrderReadDto
}

/**
 * Holds the signed-in session. Empty until a real login is wired, which is why
 * order submission fails with a clear message rather than silently doing nothing.
 */
object Session {
    var token: String? = null
    var storeId: String? = null
    var currencyCode: String = "USD"

    /** Profile of the signed-in user, for the header. */
    var userName: String? = null
    var userEmail: String? = null

    /** Active store name, shown in the header, drawer and Settings. */
    var storeName: String? = null

    val isSignedIn: Boolean get() = !token.isNullOrBlank() && !storeId.isNullOrBlank()

    /** Signs out: drops the token and store so no later request can use them. */
    fun clear() {
        token = null
        storeId = null
        currencyCode = "USD"
        userName = null
        userEmail = null
        storeName = null
    }
}

object OrdersHttp {
    val api: OrdersApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(OrdersApi::class.java)
    }
}

class OrdersRepository(private val api: OrdersApi = OrdersHttp.api) {

    suspend fun createOrder(body: OrderCreateDto): OrderReadDto {
        val token = Session.token
            ?: throw IllegalStateException("Not signed in — order was not sent to the server")
        val storeId = Session.storeId
            ?: throw IllegalStateException("No store selected — order was not sent to the server")
        return api.createOrder("Bearer $token", storeId, body)
    }
}
