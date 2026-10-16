package com.chmaba.pos.data.store

import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.readableMessage
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.HttpException
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PATCH
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

/**
 * An amount in the store's own currency.
 *
 * Mirrors the web's `formatCurrencyAmount` (apps/web/src/components/ui.jsx) so the two clients
 * cannot disagree about what a number looks like: riel is whole and carries its own sign, baht
 * takes two decimals, and anything else falls back to dollars. Before this, every currency that
 * was not KHR was rendered with a dollar sign, so a THB store read "$12.00".
 *
 * Locale.US, so a comma-decimal locale cannot corrupt an amount.
 */
fun money(value: Double, currency: String = "USD"): String = when (currency) {
    "KHR" -> String.format(Locale.US, "%,.0f", value) + "៛"
    "THB" -> "฿" + String.format(Locale.US, "%.2f", value)
    else -> "$" + String.format(Locale.US, "%.2f", value)
}

fun money(raw: String?, currency: String = "USD"): String =
    money(raw?.toDoubleOrNull() ?: 0.0, currency)

/**
 * The sign that may sit *before* an amount the cashier is still typing, for the till's field
 * prefixes. It follows [money] rather than inventing a second rule, so an input can never
 * contradict the total shown directly above it.
 *
 * KHR is deliberately empty: riel writes its sign after the figure ("1,234៛"), so there is
 * nothing that can precede a typed amount - the field's placeholder already carries the sign -
 * and prefixing it would read "៛1,234៛".
 */
fun currencyPrefix(currency: String = "USD"): String = when (currency) {
    "KHR" -> ""
    "THB" -> "฿"
    else -> "$"
}

/**
 * The cash amounts the till offers as one-tap chips, in the store's own currency.
 *
 * Each is a preset for the *whole* cash field, not an amount to add, so every one has to be at
 * least a typical sale - a chip below the total leaves the sale uncompletable, which is worse than
 * no chip at all. These are the banknotes a cashier is actually handed: 20/50/100 dollars, the
 * 100/500/1,000 baht notes, and the riel notes a small sale is paid with.
 *
 * Riel previously got 20/50/100 like everything else, which in riel is truthful and useless: a
 * customer does not hand over 50 riel, and the notes start at 100.
 */
fun cashChips(currency: String = "USD"): List<Double> = when (currency) {
    "KHR" -> listOf(10_000.0, 20_000.0, 50_000.0)
    "THB" -> listOf(100.0, 500.0, 1_000.0)
    else -> listOf(20.0, 50.0, 100.0)
}

/**
 * The discount amounts the sheet offers, in the store's own currency.
 *
 * The same problem as [cashChips] in a second place: 1/5/10 is a dollar-sized discount, and a riel
 * store was offered amounts nobody discounts by. Riel takes thousands; baht takes tens and hundreds.
 */
fun discountChips(currency: String = "USD"): List<Double> = when (currency) {
    "KHR" -> listOf(500.0, 1_000.0, 5_000.0)
    "THB" -> listOf(20.0, 50.0, 100.0)
    else -> listOf(1.0, 5.0, 10.0)
}

/**
 * The exact cash figure for [total], at the precision the currency is counted in.
 *
 * Riel is whole; everything else takes cents. "Exact" rendered two decimals for every store, so a
 * riel till filled its field with 20500.00 - an amount nobody can hand over.
 */
fun exactCash(total: Double, currency: String = "USD"): String =
    if (currency == "KHR") {
        String.format(Locale.US, "%.0f", total)
    } else {
        String.format(Locale.US, "%.2f", total)
    }

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
    @SerializedName("product_id") val productId: String? = null,
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

/**
 * Mirrors CustomerUpdateRequest. Every field is optional, and Gson omits nulls,
 * which is the PATCH semantic the API wants: absent means leave it alone.
 */
data class CustomerUpdateBody(
    @SerializedName("name") val name: String? = null,
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

/**
 * What `POST /orders/{id}/cancel` came back with.
 *
 * The endpoint answers 200 with the order, 202 when the cancellation was queued
 * for approval instead, or 409 when the store does not allow it — cancelling a
 * paid order runs through the refund engine and needs the `cancel_paid_order`
 * approval rule, so on a default policy it is refused.
 */
sealed interface CancelOutcome {
    data object Cancelled : CancelOutcome
    data object PendingApproval : CancelOutcome
    data class Refused(val message: String) : CancelOutcome
}

/** One line of a refund request. `quantity` is what is being returned. */
data class RefundItemBody(
    @SerializedName("product_id") val productId: String,
    @SerializedName("quantity") val quantity: Double,
)

/**
 * Mirrors RefundCreateRequest. `method` is "original" or "cash"; "original" puts
 * the money back the way it came in.
 */
data class RefundCreateBody(
    @SerializedName("method") val method: String = "original",
    @SerializedName("reason") val reason: String? = null,
    @SerializedName("items") val items: List<RefundItemBody>,
)

/** Mirrors RefundRead, trimmed to what the app shows. */
data class RefundDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("subtotal") val subtotal: String? = null,
)

/**
 * What `POST /orders/{id}/refund` came back with: 201 with a RefundRead, 202 when
 * the refund was queued for approval, or a refusal when the store does not allow
 * it. Same three-way shape as cancelling, and handled the same way.
 */
sealed interface RefundOutcome {
    data class Refunded(val refund: RefundDto) : RefundOutcome
    data object PendingApproval : RefundOutcome
    data class Refused(val message: String) : RefundOutcome
}

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

    /**
     * No body: `OrderCancelRequest` only carries `refund_deposit`, which applies to
     * reservations and defaults to the store's own setting.
     */
    @POST("orders/{id}/cancel")
    suspend fun cancelOrder(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
    ): Response<OrderDto>

    @POST("orders/{id}/refund")
    suspend fun refundOrder(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
        @Body body: RefundCreateBody,
    ): Response<RefundDto>

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

    /** Partial update; omitted fields are left as they are. Company-scoped. */
    @PATCH("customers/{id}")
    suspend fun updateCustomer(
        @Header("Authorization") bearer: String,
        @Path("id") id: String,
        @Body body: CustomerUpdateBody,
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

    /**
     * Cancels an order. Branches on the status code rather than the body, because
     * a 202 answers with a pending-approval payload, not an order.
     */
    suspend fun cancelOrder(id: String): CancelOutcome {
        val response = api.cancelOrder(bearer(), store(), id)
        return when {
            response.code() == 202 -> CancelOutcome.PendingApproval
            response.isSuccessful -> CancelOutcome.Cancelled
            else -> CancelOutcome.Refused(
                readableMessage(HttpException(response)) ?: "Could not cancel the order",
            )
        }
    }

    /**
     * Refunds one or more lines. Like cancelling, a 202 is not a refund: it means the
     * store's approval policy queued it, and the body is a pending-approval payload.
     */
    suspend fun refundOrder(id: String, body: RefundCreateBody): RefundOutcome {
        val response = api.refundOrder(bearer(), store(), id, body)
        return when {
            response.code() == 202 -> RefundOutcome.PendingApproval
            response.isSuccessful -> RefundOutcome.Refunded(response.body() ?: RefundDto())
            else -> RefundOutcome.Refused(
                readableMessage(HttpException(response)) ?: "Could not refund the order",
            )
        }
    }

    suspend fun customers(search: String? = null): List<CustomerDto> = api.customers(bearer(), search)

    suspend fun customer(id: String): CustomerDetailDto = api.customer(bearer(), id)

    suspend fun createCustomer(body: CustomerCreateBody): CustomerDto = api.createCustomer(bearer(), body)

    suspend fun updateCustomer(id: String, body: CustomerUpdateBody): CustomerDto =
        api.updateCustomer(bearer(), id, body)
}
