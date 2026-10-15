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
    /**
     * Whether the server keeps this session beyond a browser-style session cookie.
     * `/auth/login` reads it (v1.py:972 hands it to create_session), so the sign-in
     * screen's checkbox is a real choice rather than decoration.
     */
    @SerializedName("remember_me") val rememberMe: Boolean = false,
)

data class TokenResponseDto(
    @SerializedName("access_token") val accessToken: String? = null,
    @SerializedName("token_type") val tokenType: String? = null,
)

/** Mirrors RegisterRequest. The API takes a name, an email and a password, and nothing else. */
data class RegisterRequest(
    @SerializedName("email") val email: String,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("password") val password: String,
)

/** Mirrors RegisterResponse. The code itself only comes back in development. */
data class RegisterResponseDto(
    @SerializedName("message") val message: String? = null,
)

/** Mirrors VerifyEmailRequest: the code from the email is the token. */
data class VerifyEmailRequest(
    @SerializedName("token") val token: String,
)

data class StoreDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("currency_code") val currencyCode: String? = null,
    /**
     * The store's service tax rate. The POS charges tax at this rate, so it is read from
     * the payload rather than assumed to be the default.
     */
    @SerializedName("service_tax_rate") val serviceTaxRate: String? = null,
    /**
     * The store's preferences. Only the loyalty keys are read from it: the API awards
     * points at `loyalty_pts_per_usd` (default 1) when `loyalty_enabled` is not false,
     * and neither value is exposed anywhere else.
     */
    @SerializedName("preferences") val preferences: StorePreferencesDto? = null,
)

/** The store preference keys this app reads. Gson ignores the rest of the document. */
data class StorePreferencesDto(
    @SerializedName("loyalty_pts_per_usd") val loyaltyPointsPerUsd: Double? = null,
    @SerializedName("loyalty_enabled") val loyaltyEnabled: Boolean? = null,
)

/**
 * `GET /workspaces` returns `list[WorkspaceMembershipRead]` — a company switcher
 * (company_id, name, role, is_current). It deliberately carries **no** store, so
 * reading a store from it always yields null.
 */
/** The company the workspace belongs to. Only the name is read from it. */
data class CompanyDto(
    @SerializedName("name") val name: String? = null,
)

data class WorkspaceMembershipDto(
    @SerializedName("company_id") val companyId: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("role") val role: String? = null,
    @SerializedName("is_current") val isCurrent: Boolean = false,
)

/** `WorkspaceRead` — returned by `/workspaces/current` and `/workspaces/switch`. */
data class WorkspaceDto(
    @SerializedName("store") val store: StoreDto? = null,
    /**
     * The active plan's feature list, straight from `/workspaces/current`. The app
     * uses it to say what a plan does not include *before* the user tries an action,
     * rather than only relaying the server's 403 afterwards.
     */
    @SerializedName("company") val company: CompanyDto? = null,
    @SerializedName("plan_features") val planFeatures: List<String> = emptyList(),
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

    /**
     * Creates an account. The API asks for a Turnstile token only when the deployment has a
     * secret key configured, and this app has no way to obtain one, so none is sent.
     */
    @POST("auth/register")
    suspend fun register(@Body body: RegisterRequest): RegisterResponseDto

    /** Confirms the emailed code. Answers 400 when the code is wrong or has expired. */
    @POST("auth/verify-email")
    suspend fun verifyEmail(@Body body: VerifyEmailRequest): UserDto
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

    /**
     * Registers an account and returns the server's own message. A duplicate email comes
     * back as 409 with "An account with this email already exists".
     */
    suspend fun register(email: String, fullName: String, password: String): Result<String> {
        return try {
            val message = api.register(
                RegisterRequest(
                    email = email.trim(),
                    fullName = fullName.trim(),
                    password = password,
                ),
            ).message
            Result.success(message ?: "Check your email for the confirmation code.")
        } catch (problem: Exception) {
            Result.failure(problem)
        }
    }

    /** Confirms the emailed code, which is what makes the account usable for sign-in. */
    suspend fun verifyEmail(code: String): Result<Unit> {
        return try {
            api.verifyEmail(VerifyEmailRequest(code.trim()))
            Result.success(Unit)
        } catch (problem: Exception) {
            Result.failure(problem)
        }
    }

    suspend fun signIn(email: String, password: String, remember: Boolean = false): Result<String> {
        return try {
            val token = api.login(
                LoginRequest(email = email.trim(), password = password, rememberMe = remember),
            ).accessToken
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
        Session.serviceTaxRate = store.serviceTaxRate ?: Session.DEFAULT_SERVICE_TAX_RATE
            Session.storeName = store.name
        Session.companyName = workspace.company?.name
        Session.loyaltyPointsPerUsd =
            store.preferences?.loyaltyPointsPerUsd ?: Session.DEFAULT_LOYALTY_POINTS_PER_USD
        Session.loyaltyEnabled = store.preferences?.loyaltyEnabled ?: true
            // Kept so screens can explain a plan limit instead of only surfacing a 403.
            Session.planFeatures = workspace.planFeatures.toSet()

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
