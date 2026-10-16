package com.chmaba.pos.data.support

import com.chmaba.pos.data.orders.Session
import com.chmaba.pos.data.plans.ApiClient
import com.google.gson.annotations.SerializedName
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.GET
import retrofit2.http.Header

/**
 * The help corpus, as `GET /support/articles` returns it.
 *
 * The API has already filtered for the reader: `filter_sections` narrows on the company's vertical
 * and the member's role (v1.py:1728), so the app renders what it is given rather than deciding what
 * someone may read. Mirrors SupportSectionRead -> SupportArticleRead.
 *
 * The articles are the same ones the web POS shows, and their steps describe the POS rather than
 * one client of it - a step that says "from the sidebar" is the web's chrome. That is the API's
 * copy, not something this screen rewrites.
 */
data class SupportSectionDto(
    @SerializedName("id") val id: String = "",
    @SerializedName("title") val title: String = "",
    @SerializedName("blurb") val blurb: String = "",
    @SerializedName("articles") val articles: List<SupportArticleDto> = emptyList(),
)

/** Mirrors SupportArticleRead; `tip` is optional and most articles carry none. */
data class SupportArticleDto(
    @SerializedName("id") val id: String = "",
    @SerializedName("title") val title: String = "",
    @SerializedName("steps") val steps: List<String> = emptyList(),
    @SerializedName("tip") val tip: String? = null,
)

interface SupportApi {
    @GET("support/articles")
    suspend fun articles(@Header("Authorization") bearer: String): List<SupportSectionDto>
}

object SupportHttp {
    val api: SupportApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SupportApi::class.java)
    }
}

class SupportRepository(private val api: SupportApi = SupportHttp.api) {

    private fun bearer(): String =
        "Bearer " + (Session.token ?: throw IllegalStateException("Not signed in"))

    suspend fun sections(): List<SupportSectionDto> = api.articles(bearer())
}
