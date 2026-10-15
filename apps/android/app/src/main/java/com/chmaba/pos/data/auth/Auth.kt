package com.chmaba.pos.data.auth

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

/** Mirrors the API's TokenResponse. */
data class LoginRequest(
    @SerializedName("email") val email: String,
    @SerializedName("password") val password: String,
)

data class TokenResponseDto(
    @SerializedName("access_token") val accessToken: String? = null,
    @SerializedName("token_type") val tokenType: String? = null,
)

data class StoreDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("currency_code") val currencyCode: String? = null,
)

/**
 * `GET /workspaces` returns `list[WorkspaceMembershipRead]` — a company switcher
 * (company_id, name, role, is_current). It deliberately carries **no** store, so
 * reading a store from it always yields null.
 */
data class WorkspaceMembershipDto(
    @SerializedName("company_id") val companyId: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("role") val role: String? = null,
    @SerializedName("is_current") val isCurrent: Boolean = false,
)

/** `WorkspaceRead` — returned by `/workspaces/current` and `/workspaces/switch`. */
data class WorkspaceDto(
    @SerializedName("store") val store: StoreDto? = null,
)

/** Mirrors UserRead — `GET /auth/me`. Drives the header profile. */
data class UserDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("email") val email: String? = null,
    @SerializedName("full_name") val fullName: String? = null,
)

interface AuthApi {
    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponseDto

    /** Company switcher only — no store field. */
    @GET("workspaces")
    suspend fun workspaces(@Header("Authorization") bearer: String): List<WorkspaceMembershipDto>

    /** The active workspace, including its store. This is what opens a session. */
    @GET("workspaces/current")
    suspend fun currentWorkspace(@Header("Authorization") bearer: String): WorkspaceDto

    /** The signed-in user, for the header profile. */
    @GET("auth/me")
    suspend fun me(@Header("Authorization") bearer: String): UserDto
}

object AuthHttp {
    val api: AuthApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(AuthApi::class.java)
    }
}

/**
 * Signs in and populates [Session]. The store is taken from the first
 * workspace, which is what the web client does after login.
 */
class AuthRepository(private val api: AuthApi = AuthHttp.api) {

    suspend fun signIn(email: String, password: String): Result<String> {
        return try {
            val token = api.login(LoginRequest(email.trim(), password)).accessToken
            if (token.isNullOrBlank()) {
                Result.failure(IllegalStateException("The server did not return a token"))
            } else {
                openSession(token)
            }
        } catch (problem: Exception) {
            Result.failure(problem)
        }
    }

    /** Opens a session from an existing token — used by the Google deep link. */
    suspend fun openSession(token: String): Result<String> {
        // Published before the first request on purpose. SessionInterceptor decides
        // whether to renew by reading Session.token, so with it unset a cold start
        // holding an expired token skipped renewal entirely and fell to Login.
        Session.token = token
        return try {
            // /workspaces is only a company switcher and carries no store, so the
            // active workspace has to be read from /workspaces/current.
            val workspace = api.currentWorkspace("Bearer $token")
            val store = workspace.store
                ?: return Result.failure(
                    IllegalStateException(
                        "This account has no store yet. Create your workspace on chmaba.com, then sign in again.",
                    ),
                )

            Session.token = token
            Session.storeId = store.id
            Session.currencyCode = store.currencyCode ?: "USD"
            Session.storeName = store.name

            // Profile for the header. A failure here must not block sign-in.
            val user = runCatching { api.me("Bearer $token") }.getOrNull()
            Session.userName = user?.fullName
            Session.userEmail = user?.email

            // Persist so the session survives the app being killed.
            SessionStore.save(token, user?.fullName, user?.email)

            Result.success(store.name ?: "Your store")
        } catch (problem: Exception) {
            // Do not leave a token behind that we could not use; AppRoot falls back
            // to Login and the next attempt must start clean.
            Session.token = null
            Result.failure(problem)
        }
    }

    /**
     * Restores a previously saved session on launch. Returns the store name when
     * the token is still valid, or a failure so the caller falls back to Login.
     */
    suspend fun restore(): Result<String> {
        val saved = SessionStore.token()
            ?: return Result.failure(IllegalStateException("No saved session"))
        return openSession(saved)
    }
}
