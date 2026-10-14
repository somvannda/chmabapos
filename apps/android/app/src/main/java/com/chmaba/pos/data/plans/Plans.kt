package com.chmaba.pos.data.plans

import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import java.util.Locale

/**
 * Mirrors the API's `PlanRead` (chmabapos_api/app/schemas.py).
 *
 * `marketing_features` is DERIVED SERVER-SIDE by
 * `derive_plan_marketing_features()` in app/features.py, so the client renders
 * whatever the API returns and never authors its own feature bullets.
 *
 * The API serialises Decimal as a JSON string (e.g. "19.00"), so
 * `monthly_price` stays a String here and is parsed where it is formatted.
 */
data class PlanDto(
    @SerializedName("code") val code: String = "",
    @SerializedName("name") val name: String = "",
    @SerializedName("monthly_price") val monthlyPrice: String? = null,
    @SerializedName("max_stores") val maxStores: Int = 0,
    @SerializedName("max_members") val maxMembers: Int = 0,
    @SerializedName("transaction_limit") val transactionLimit: Int = 0,
    @SerializedName("description") val description: String? = null,
    @SerializedName("capabilities") val capabilities: Map<String, Boolean> = emptyMap(),
    @SerializedName("marketing_features") val marketingFeatures: List<String> = emptyList(),
    @SerializedName("is_active") val isActive: Boolean = true,
) {
    val pricePerMonthValue: Double
        get() = monthlyPrice?.toDoubleOrNull() ?: 0.0
}

/**
 * Billing cycles. These multipliers and discounts are duplicated client-side by
 * the web app in `apps/web/src/features/marketing.jsx` (BILLING_CYCLES) and must
 * stay identical — change one and the two products disagree on price.
 *
 * If a third client appears, this table should move to the API instead.
 */
enum class BillingCycle(
    val key: String,
    val label: String,
    val multiplier: Int,
    val discount: Double,
    val badge: String?,
    val billedLabel: String,
) {
    Monthly("monthly", "Monthly", 1, 0.0, null, "billed monthly"),
    SemiAnnual("semi_annual", "Semi-annual", 6, 0.15, "Save 15%", "billed every 6 months"),
    Annual("annual", "Annual", 12, 0.20, "Save 20%", "billed annually"),
}

// ---- price maths, exactly as the web computes it -------------------------

fun PlanDto.isFree(): Boolean = pricePerMonthValue <= 0.0

fun PlanDto.pricePerMonth(cycle: BillingCycle): Double =
    pricePerMonthValue * (1.0 - cycle.discount)

/** "$0" for a free plan, otherwise the per-month price to 2 decimals.
 *  Locale.US is explicit: on a comma-decimal locale (e.g. fr) the default
 *  would render "16,15" and the price would be wrong on screen. */
fun PlanDto.priceLabel(cycle: BillingCycle): String =
    if (isFree()) "$0" else "$" + String.format(Locale.US, "%.2f", pricePerMonth(cycle))

/** Total for the whole billing period, or null when the plan is free. */
fun PlanDto.totalFor(cycle: BillingCycle): String? =
    if (isFree()) null else String.format(Locale.US, "%.2f", pricePerMonth(cycle) * cycle.multiplier)

/** The web highlights the "starter" plan, else the first paid plan. */
fun List<PlanDto>.featuredCode(): String? =
    firstOrNull { it.code == "starter" }?.code
        ?: firstOrNull { it.pricePerMonthValue > 0.0 }?.code

// ---- transport -----------------------------------------------------------

interface ChmabaApi {
    /** Public endpoint — no token, same one the web calls via api.plans(). */
    @GET("plans")
    suspend fun plans(): List<PlanDto>
}

object ApiClient {
    /**
     * The app talks to the **Vite dev-server origin**, exactly like the web app
     * does (`window.location.origin + /api/v1` in apps/web/src/api.js), and Vite
     * proxies `/api` on to the API (VITE_DEV_API_TARGET, currently
     * http://127.0.0.1:8001).
     *
     * This indirection matters for Google sign-in: the OAuth `state` is held in
     * a CSRF cookie. The authorize request and Google's callback must therefore
     * be served by the *same host* — https://localhost:5173. Calling the API
     * port directly would set the cookie on a different host and the callback's
     * state check would fail.
     *
     * `localhost` (not 127.0.0.1) is required because GOOGLE_REDIRECT_URI is
     * registered as http://localhost:5173/... and cookies are per-host.
     *
     * Reachable from the emulator via:  adb reverse tcp:5173 tcp:5173
     */
    const val BASE_URL: String = "http://localhost:5173/api/v1/"

    val api: ChmabaApi by lazy {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(logging)
            .build()
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ChmabaApi::class.java)
    }
}

class PlansRepository(private val api: ChmabaApi = ApiClient.api) {
    /** Inactive plans are filtered client-side; the public list may include them. */
    suspend fun plans(activeOnly: Boolean = true): List<PlanDto> {
        val rows = api.plans()
        return if (activeOnly) rows.filter { it.isActive } else rows
    }
}
