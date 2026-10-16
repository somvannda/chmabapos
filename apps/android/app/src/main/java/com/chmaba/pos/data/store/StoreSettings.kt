package com.chmaba.pos.data.store

import com.chmaba.pos.data.auth.StoreDto
import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.PATCH
import retrofit2.http.Path

/**
 * The store fields `PATCH /stores/{id}` accepts, mirroring `StoreUpdateRequest`.
 *
 * The API takes more than this - the tax rate, the currency, the receipt preferences and the
 * payment link all travel in the same request - but this app only offers the four that are a text
 * field and nothing else. The others need a decision first (which currencies the company accepts,
 * what a receipt says), so they stay notices in Settings rather than half-built forms here.
 */
data class StoreUpdateDto(
    @SerializedName("name") val name: String,
    @SerializedName("address") val address: String? = null,
    @SerializedName("phone") val phone: String? = null,
    @SerializedName("email") val email: String? = null,
    /**
     * What the till charges, as a decimal string. The POS reads it from `Session.serviceTaxRate`,
     * which the store-details screen updates from what this returns, so a saved rate is in force
     * without a restart.
     */
    @SerializedName("service_tax_rate") val serviceTaxRate: String? = null,
)

/**
 * Why this tax rate cannot be saved, or null when it can.
 *
 * The API takes a decimal, so anything a person might type - "10%", "ten", an empty box - is caught
 * here rather than sent, because a 422 naming a field the reader cannot see helps nobody. The
 * ceiling is the server's business; this insists on a number that is not negative and not
 * over-precise for a percentage.
 */
fun taxRateProblem(value: String): String? {
    val trimmed = value.trim()
    if (trimmed.isEmpty()) return "A tax rate is needed. Enter 0 for none."
    val number = trimmed.toDoubleOrNull() ?: return "The tax rate has to be a number, like 10 or 7.5."
    if (number < 0) return "A tax rate cannot be negative."
    if (trimmed.substringAfter('.', "").length > 2) return "Use at most two decimal places."
    return null
}

interface StoreSettingsApi {
    @PATCH("stores/{id}")
    suspend fun updateStore(
        @Header("Authorization") bearer: String,
        @Path("id") id: String,
        @Body body: StoreUpdateDto,
    ): StoreDto
}

object StoreSettingsHttp {
    val api: StoreSettingsApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(StoreSettingsApi::class.java)
    }
}

class StoreSettingsRepository(private val api: StoreSettingsApi = StoreSettingsHttp.api) {

    /**
     * Saves the store the session is working in. Answers with the store as the server now holds
     * it, which is what the screen shows rather than what was typed - the API trims and may
     * normalise, and only one of the two is the truth.
     */
    suspend fun update(body: StoreUpdateDto): StoreDto {
        val token = Session.token
            ?: throw IllegalStateException("Not signed in - the store was not saved")
        val storeId = Session.storeId
            ?: throw IllegalStateException("No store selected - the store was not saved")
        return api.updateStore("Bearer $token", storeId, body)
    }
}
