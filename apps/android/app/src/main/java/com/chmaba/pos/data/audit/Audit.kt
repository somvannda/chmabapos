package com.chmaba.pos.data.audit

import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Header
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * One recorded change, as `GET /audit-logs` returns it.
 *
 * That endpoint declares no response model (v1.py:8990), so this mirrors the dict the API actually
 * sends: who did it, the action key, what was acted on, and a free-form details map whose keys
 * differ per action - which is why [details] is not modelled field by field.
 */
data class AuditEntryDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("action") val action: String = "",
    @SerializedName("entity_type") val entityType: String? = null,
    @SerializedName("entity_id") val entityId: String? = null,
    /** The person's display name. Absent where the system made the change. */
    @SerializedName("actor") val actor: String? = null,
    @SerializedName("details") val details: Map<String, Any?>? = null,
    @SerializedName("created_at") val createdAt: String? = null,
)

/**
 * The API's instant rendered in the reader's own zone.
 *
 * The payload carries an offset ("+00:00"), so slicing the string would show UTC on a phone that
 * is not in it - a sale rung up at 11:35 in Phnom Penh reading as 04:35. A value that cannot be
 * parsed is returned as it came rather than replaced with a guess.
 */
fun localStamp(iso: String?, zone: ZoneId = ZoneId.systemDefault()): String {
    if (iso.isNullOrBlank()) return ""
    return try {
        OffsetDateTime.parse(iso)
            .atZoneSameInstant(zone)
            .format(DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.US))
    } catch (problem: Exception) {
        iso
    }
}

interface AuditApi {
    @GET("audit-logs")
    suspend fun auditLogs(@Header("Authorization") bearer: String): List<AuditEntryDto>
}

object AuditHttp {
    val api: AuditApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(AuditApi::class.java)
    }
}

class AuditRepository(private val api: AuditApi = AuditHttp.api) {

    private fun bearer(): String =
        "Bearer " + (Session.token ?: throw IllegalStateException("Not signed in"))

    suspend fun entries(): List<AuditEntryDto> = api.auditLogs(bearer())
}
