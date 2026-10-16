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
)

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
