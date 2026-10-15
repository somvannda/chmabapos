package com.chmaba.pos.data.auth

import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST

/** Mirrors PasswordResetRequest. */
data class PasswordResetRequestBody(
    @SerializedName("email") val email: String,
)

/** The endpoint answers `{"message": "..."}`, and says the same thing whether the email exists. */
data class PasswordResetResponse(
    @SerializedName("message") val message: String? = null,
)

/**
 * Asking for a password reset.
 *
 * Only the request half is here. The API emails a link carrying the token, and that link
 * opens the web app, which is where the reset is finished - this app has no screen that can
 * consume a token, so it does not pretend to set a password. Its own interface, rather than
 * an addition to [AuthApi], so it cannot collide with the sign-up work in flight.
 */
interface PasswordResetApi {
    @POST("auth/request-password-reset")
    suspend fun request(@Body body: PasswordResetRequestBody): PasswordResetResponse
}

object PasswordResetHttp {
    val api: PasswordResetApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(PasswordResetApi::class.java)
    }
}

class PasswordResetRepository(private val api: PasswordResetApi = PasswordResetHttp.api) {

    /**
     * Asks the API to email a reset link and returns its own message. The API answers the
     * same way whether or not the address belongs to an account, on purpose, so this cannot
     * be used to discover which addresses have accounts.
     */
    suspend fun request(email: String): Result<String> {
        return try {
            val message = api.request(PasswordResetRequestBody(email.trim())).message
            Result.success(
                message
                    ?: "If an active account exists for this email, a reset link has been sent",
            )
        } catch (problem: Exception) {
            Result.failure(problem)
        }
    }
}
