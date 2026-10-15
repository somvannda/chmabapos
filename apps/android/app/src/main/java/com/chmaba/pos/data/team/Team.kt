package com.chmaba.pos.data.team

import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Header

/**
 * The people who can sign in to this company.
 *
 * Mirrors `GET /team` -> `list[MembershipRead]` (chmabapos_api/app/schemas.py). The endpoint is
 * company-scoped, so it takes no store header. The person's name and email sit in the nested
 * user, and the role is the API's own lowercase key ("owner"), which is a label's input rather
 * than a label.
 */
data class MembershipDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("user_id") val userId: String? = null,
    @SerializedName("role") val role: String = "",
    @SerializedName("status") val status: String = "",
    @SerializedName("user") val user: TeamUserDto? = null,
    /** The stores this member reaches. An empty list means the whole company. */
    @SerializedName("store_ids") val storeIds: List<String> = emptyList(),
)

/** The nested UserRead that MembershipRead carries; only the fields a row shows. */
data class TeamUserDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("email") val email: String = "",
    @SerializedName("full_name") val fullName: String? = null,
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("is_email_verified") val isEmailVerified: Boolean = false,
)

interface TeamApi {
    @GET("team")
    suspend fun team(@Header("Authorization") bearer: String): List<MembershipDto>
}

object TeamHttp {
    val api: TeamApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(TeamApi::class.java)
    }
}

class TeamRepository(private val api: TeamApi = TeamHttp.api) {

    private fun bearer(): String =
        "Bearer " + (Session.token ?: throw IllegalStateException("Not signed in"))

    suspend fun members(): List<MembershipDto> = api.team(bearer())
}
