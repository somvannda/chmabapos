package com.chmaba.pos.data.reports

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.chmaba.pos.data.store.LoadState
import com.google.gson.annotations.SerializedName
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Query
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone
import kotlin.math.roundToInt

// ---------------------------------------------------------------------------
// Date helpers. minSdk is 24 and core-library desugaring is off, so java.time
// is not available; Calendar is.
// ---------------------------------------------------------------------------

private fun dayIso(daysAgo: Int = 0): String {
    val calendar = Calendar.getInstance()
    calendar.add(Calendar.DAY_OF_MONTH, -daysAgo)
    return "%04d-%02d-%02d".format(
        calendar.get(Calendar.YEAR),
        calendar.get(Calendar.MONTH) + 1,
        calendar.get(Calendar.DAY_OF_MONTH),
    )
}

private fun monthStartIso(): String {
    val calendar = Calendar.getInstance()
    calendar.set(Calendar.DAY_OF_MONTH, 1)
    return "%04d-%02d-%02d".format(
        calendar.get(Calendar.YEAR),
        calendar.get(Calendar.MONTH) + 1,
        calendar.get(Calendar.DAY_OF_MONTH),
    )
}

/**
 * Reporting windows. These mirror the web presets exactly:
 * apps/web/src/lib/dashboard.js `dashboardPeriods` (today / week / month) and
 * the preset list in apps/web/src/features/reports.jsx (which adds 30 days and
 * all time).
 */
enum class ReportPeriod(val label: String, val from: String, val to: String?) {
    Today("Today", dayIso(0), dayIso(0)),
    Week("Last 7 days", dayIso(6), dayIso(0)),
    Month30("Last 30 days", dayIso(29), dayIso(0)),
    ThisMonth("This month", monthStartIso(), dayIso(0)),
    AllTime("All time", "1970-01-01", null),
}

// ---------------------------------------------------------------------------
// Payload. Mirrors ReportSummary (chmabapos_api/app/schemas.py:2453). The
// breakdown lists are untyped dicts server-side; their keys are taken from the
// route body (api/v1.py:7993) and the web helpers (lib/dashboard.js:132-175):
//   top_products      -> name / quantity / amount
//   daily_sales       -> date / amount
//   category_sales    -> category / amount
//   payment_methods   -> method / amount
// transactions_detail is typed server-side (ReportTransactionRead).
// ---------------------------------------------------------------------------

data class TopProductDto(
    @SerializedName("name") val name: String? = null,
    @SerializedName("quantity") val quantity: Double = 0.0,
    @SerializedName("amount") val amount: String? = null,
) {
    val value: Double get() = amount?.toDoubleOrNull() ?: 0.0
    val units: Int get() = quantity.roundToInt()
}

data class MixRowDto(
    @SerializedName("method") val method: String? = null,
    @SerializedName("category") val category: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("amount") val amount: String? = null,
) {
    /** The web labels a mix row method || category || name. */
    val label: String get() = method ?: category ?: name ?: "Other"
    val value: Double get() = amount?.toDoubleOrNull() ?: 0.0
}

data class DailySaleDto(
    @SerializedName("date") val date: String? = null,
    @SerializedName("amount") val amount: String? = null,
) {
    val value: Double get() = amount?.toDoubleOrNull() ?: 0.0
}

data class ReportTransactionDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("order_number") val orderNumber: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("currency_code") val currencyCode: String? = null,
    @SerializedName("total") val total: String? = null,
    @SerializedName("items_count") val itemsCount: Int = 0,
    @SerializedName("units_count") val unitsCount: Int = 0,
    @SerializedName("payment_method") val paymentMethod: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
) {
    /**
     * "10:42 AM". created_at is UTC; parsed as UTC and rendered in the device
     * timezone. The store timezone is not available client-side, so a device in
     * a different zone from the store will show the clock shifted.
     */
    val timeLabel: String get() = formatClock(createdAt)
}

data class ReportSummaryDto(
    @SerializedName("from_date") val fromDate: String? = null,
    @SerializedName("to_date") val toDate: String? = null,
    @SerializedName("gross_sales") val grossSales: String? = null,
    @SerializedName("net_sales") val netSales: String? = null,
    @SerializedName("net_after_refunds") val netAfterRefunds: String? = null,
    @SerializedName("tax") val tax: String? = null,
    @SerializedName("discounts") val discounts: String? = null,
    @SerializedName("refunds") val refunds: String? = null,
    @SerializedName("refunds_count") val refundsCount: Int = 0,
    @SerializedName("transactions") val transactions: Int = 0,
    @SerializedName("average_order") val averageOrder: String? = null,
    @SerializedName("items_sold") val itemsSold: Double = 0.0,
    @SerializedName("days_in_period") val daysInPeriod: Int = 1,
    @SerializedName("average_daily_net") val averageDailyNet: String? = null,
    @SerializedName("projected_next_30_days") val projectedNext30Days: String? = null,
    @SerializedName("top_products") val topProducts: List<TopProductDto> = emptyList(),
    @SerializedName("daily_sales") val dailySales: List<DailySaleDto> = emptyList(),
    @SerializedName("category_sales") val categorySales: List<MixRowDto> = emptyList(),
    @SerializedName("payment_methods") val paymentMethods: List<MixRowDto> = emptyList(),
    @SerializedName("transactions_detail") val transactionsDetail: List<ReportTransactionDto> = emptyList(),
) {
    /**
     * The headline figure the web uses first: net after refunds, falling back to
     * net sales (lib/dashboard.js:195 does `net_after_refunds ?? net_sales`).
     */
    val effectiveNetRaw: String get() = netAfterRefunds ?: netSales ?: "0.00"

    /** Taken from the payload rather than assumed, so a non-USD store is right. */
    val currency: String get() = transactionsDetail.firstOrNull()?.currencyCode ?: "USD"

    val averagePerDay: Double
        get() = if (daysInPeriod > 0) transactions.toDouble() / daysInPeriod else 0.0
}

private fun formatClock(raw: String?): String {
    // FastAPI emits e.g. 2024-10-08T10:42:00.123456+00:00; the leading 19 chars
    // are the wall clock, which is all we parse.
    val stamp = raw?.take(19) ?: return "—"
    return try {
        val input = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
            .apply { timeZone = TimeZone.getTimeZone("UTC") }
        SimpleDateFormat("h:mm a", Locale.US).format(input.parse(stamp)!!)
    } catch (_: Exception) {
        "—"
    }
}

/** One ranked row of a breakdown, already carrying its share of the total. */
data class MixShare(val label: String, val amount: Double, val percent: Int)

/**
 * Mirrors apps/web/src/lib/dashboard.js `salesMix`: drop zero rows, rank by
 * amount descending, keep [limit], and express each as a share of the sum of
 * the rows that were kept.
 */
fun salesMix(rows: List<MixRowDto>, limit: Int = 5): List<MixShare> {
    val clean = rows.map { it.label to it.value }
        .filter { it.second > 0 }
        .sortedByDescending { it.second }
    val total = clean.sumOf { it.second }
    return clean.take(limit).map { (label, amount) ->
        MixShare(label, amount, if (total > 0) ((amount / total) * 100).roundToInt() else 0)
    }
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

interface ReportsApi {
    @GET("reports/summary")
    suspend fun summary(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("from_date") fromDate: String? = null,
        @Query("to_date") toDate: String? = null,
    ): ReportSummaryDto
}

object ReportsHttp {
    val api: ReportsApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ReportsApi::class.java)
    }
}

class ReportsRepository(private val api: ReportsApi = ReportsHttp.api) {
    suspend fun summary(fromDate: String?, toDate: String?): ReportSummaryDto {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val store = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.summary("Bearer $token", store, fromDate, toDate)
    }
}

/**
 * Shared by the Dashboard and the Reports screen. Both read the same summary
 * and the same selected window, so there is one loader rather than two that
 * could disagree about what "today" means.
 */
class ReportsViewModel(
    private val repository: ReportsRepository = ReportsRepository(),
) : ViewModel() {

    var state: LoadState<ReportSummaryDto> by mutableStateOf(LoadState.Loading)
        private set

    var period: ReportPeriod by mutableStateOf(ReportPeriod.Today)
        private set

    init { load(ReportPeriod.Today) }

    /** Switching windows refetches; re-picking the current one does not. */
    fun select(next: ReportPeriod) {
        if (next != period) load(next)
    }

    /** Retry for the failure state. */
    fun reload() = load(period)

    private fun load(target: ReportPeriod) {
        period = target
        state = LoadState.Loading
        viewModelScope.launch {
            state = try {
                LoadState.Ready(repository.summary(target.from, target.to))
            } catch (problem: Exception) {
                LoadState.Failed(problem.message ?: "Could not load the report")
            }
        }
    }
}
