package com.chmaba.pos.data.catalog

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
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Product catalogue, mirroring the API's ProductRead
 * (chmabapos_api/app/schemas.py). `price` and the other money fields are
 * Decimals serialised as strings, and stock lives in `on_hand`.
 */
data class CategoryDto(
    @SerializedName("name") val name: String? = null,
)

data class ProductDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("sku") val sku: String = "",
    @SerializedName("price") val price: String? = null,
    @SerializedName("cost_price") val costPrice: String? = null,
    @SerializedName("tax_rate") val taxRate: String? = null,
    @SerializedName("barcode") val barcode: String? = null,
    @SerializedName("brand") val brand: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("unit") val unit: String = "each",
    @SerializedName("track_inventory") val trackInventory: Boolean = true,
    @SerializedName("track_serials") val trackSerials: Boolean = false,
    @SerializedName("category_id") val categoryId: String? = null,
    @SerializedName("on_hand") val onHand: Double = 0.0,
    @SerializedName("reorder_point") val reorderPoint: Int = 10,
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("image") val image: String? = null,
    @SerializedName("category") val category: CategoryDto? = null,
    /** The product's variants, so the editor can show what it already has. */
    @SerializedName("variants") val variants: List<ProductVariantDto> = emptyList(),
    /** The one modifier group offered when this product is rung up. */
    @SerializedName("modifier_group_id") val modifierGroupId: String? = null,
)

/** Mirrors ModifierRead. `price_delta` is a Decimal serialised as a string. */
data class ModifierDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("price_delta") val priceDelta: String? = null,
)

/** Mirrors ModifierGroupRead, which `GET /modifier-groups` returns. */
data class ModifierGroupDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("min_select") val minSelect: Int = 0,
    @SerializedName("max_select") val maxSelect: Int = 1,
    @SerializedName("is_required") val isRequired: Boolean = false,
    @SerializedName("modifiers") val modifiers: List<ModifierDto> = emptyList(),
)

/**
 * Body for `POST /products` and `PATCH /products/{id}`, mirroring
 * ProductCreateRequest / ProductUpdateRequest. Gson omits null fields, which is
 * the PATCH semantic the API wants: an absent key means "leave this alone".
 *
 * `openingStock` and `reorderPoint` exist only on the create request, so the
 * editor leaves them null when updating.
 */
data class ProductWriteBody(
    @SerializedName("name") val name: String,
    @SerializedName("sku") val sku: String,
    @SerializedName("price") val price: String,
    @SerializedName("cost_price") val costPrice: String? = null,
    @SerializedName("tax_rate") val taxRate: String? = null,
    @SerializedName("category_id") val categoryId: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("barcode") val barcode: String? = null,
    @SerializedName("brand") val brand: String? = null,
    @SerializedName("track_inventory") val trackInventory: Boolean = true,
    @SerializedName("track_serials") val trackSerials: Boolean = false,
    @SerializedName("opening_stock") val openingStock: String? = null,
    @SerializedName("reorder_point") val reorderPoint: Int? = null,
)

/** Mirrors ProductVariantRead, trimmed to what the editor shows. */
data class ProductVariantDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String = "",
    @SerializedName("sku") val sku: String = "",
    @SerializedName("price") val price: String? = null,
    /** A variant keeps its own balance; the product's own row stays at zero. */
    @SerializedName("on_hand") val onHand: Double = 0.0,
)

/** Mirrors ProductVariantInput. An existing row keeps its `id` so it is updated, not replaced. */
data class VariantWriteBody(
    @SerializedName("id") val id: String? = null,
    @SerializedName("name") val name: String,
    @SerializedName("sku") val sku: String,
    @SerializedName("price") val price: String? = null,
)

/** Mirrors ProductVariantsSetRequest. The list is the authoritative set. */
data class VariantsSetBody(
    @SerializedName("variants") val variants: List<VariantWriteBody>,
)

/** Mirrors ProductSerialRead. Only the fields the picker needs are read. */
data class ProductSerialDto(
    @SerializedName("id") val id: String? = null,
    @SerializedName("serial_number") val serialNumber: String = "",
    @SerializedName("imei") val imei: String? = null,
    @SerializedName("store_id") val storeId: String? = null,
    @SerializedName("variant_id") val variantId: String? = null,
    @SerializedName("status") val status: String = "in_stock",
)

/** Mirrors ProductSerialInput. The number is the only required field. */
data class ProductSerialWriteBody(
    @SerializedName("serial_number") val serialNumber: String,
    /**
     * The variant the unit belongs to. A variant product keeps its stock per
     * variant, so a unit without one is counted nowhere; omitted when null, the
     * same way Gson treats every other absent field.
     */
    @SerializedName("variant_id") val variantId: String? = null,
)

/** Mirrors ProductSerialsSetRequest. */
data class ProductSerialsSetBody(
    @SerializedName("serials") val serials: List<ProductSerialWriteBody>,
)

interface ProductsApi {
    @GET("products")
    suspend fun products(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Query("active_only") activeOnly: Boolean = true,
    ): List<ProductDto>

    /**
     * Modifier groups are company-scoped: the web calls this with a token and no
     * store header, so it is not an X-Store-ID request.
     */
    @GET("modifier-groups")
    suspend fun modifierGroups(
        @Header("Authorization") bearer: String,
    ): List<ModifierGroupDto>

    /**
     * Records units against a product. Every number accepted adds one unit to the store's
     * balance server-side (v1.py:3561), and a number that already exists is refused, so
     * re-submitting the same list cannot inflate stock.
     */
    /**
     * One photo per product. The endpoint takes a single `file: UploadFile = File(...)` field, so
     * the part must be named and typed; the server stores it and answers with the product.
     */
    @retrofit2.http.Multipart
    @POST("products/{id}/image")
    suspend fun uploadProductImage(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part,
    ): ProductDto

    @POST("products/{id}/serials")
    suspend fun addSerials(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
        @Body body: ProductSerialsSetBody,
    ): List<ProductSerialDto>

    @POST("products")
    suspend fun createProduct(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Body body: ProductWriteBody,
    ): ProductDto

    @PATCH("products/{id}")
    suspend fun updateProduct(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
        @Body body: ProductWriteBody,
    ): ProductDto

    /**
     * Replaces the product's variants with the given set. A row that carries its id
     * is updated; rows left out are removed. Not plan-gated, unlike refunds.
     */
    @PUT("products/{id}/variants")
    suspend fun setVariants(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
        @Body body: VariantsSetBody,
    ): ProductDto

    /**
     * The units on the shelf for a product, which is what a sale of a serial-tracked product
     * has to name. Units attributed to another store are filtered out by the caller, as the
     * web POS does.
     */
    @GET("products/{id}/serials")
    suspend fun serials(
        @Header("Authorization") bearer: String,
        @Header("X-Store-ID") storeId: String,
        @Path("id") id: String,
        @Query("status") status: String = "in_stock",
    ): List<ProductSerialDto>
}

object CatalogHttp {
    val api: ProductsApi by lazy {
        Retrofit.Builder()
            .baseUrl(ApiClient.BASE_URL)
            .client(ApiClient.http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ProductsApi::class.java)
    }
}

class CatalogRepository(private val api: ProductsApi = CatalogHttp.api) {

    suspend fun products(): List<ProductDto> {
        val token = Session.token
            ?: throw IllegalStateException("Not signed in — showing no products")
        val storeId = Session.storeId
            ?: throw IllegalStateException("No store selected for this account")
        return api.products("Bearer $token", storeId)
    }

    /** Company-scoped, so no store header is needed. */
    suspend fun modifierGroups(): List<ModifierGroupDto> {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        return api.modifierGroups("Bearer $token")
    }

    suspend fun createProduct(body: ProductWriteBody): ProductDto {        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.createProduct("Bearer $token", storeId, body)
    }

    suspend fun updateProduct(id: String, body: ProductWriteBody): ProductDto {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.updateProduct("Bearer $token", storeId, id, body)
    }

    /** The list replaces the product's variants; rows left out are removed. */
    suspend fun setVariants(id: String, body: VariantsSetBody): ProductDto {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.setVariants("Bearer $token", storeId, id, body)
    }

    /** The sellable units for a product, for the POS's serial picker. */
    suspend fun serials(productId: String): List<ProductSerialDto> {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.serials("Bearer $token", storeId, productId)
    }

    /** Uploads a product's photo. The part is built by `productImagePart`, which names it "file". */
    suspend fun uploadProductImage(productId: String, file: okhttp3.MultipartBody.Part): ProductDto {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.uploadProductImage("Bearer $token", storeId, productId, file)
    }

    /**
     * Records units for a product, and answers with the units now on the product.
     * [variantId] is required by the form when the product is sold in variants:
     * without it the API cannot count the unit into any balance.
     */
    suspend fun addSerials(productId: String, variantId: String?, numbers: List<String>): List<ProductSerialDto> {
        val token = Session.token ?: throw IllegalStateException("Not signed in")
        val storeId = Session.storeId ?: throw IllegalStateException("No store selected for this account")
        return api.addSerials(
            "Bearer $token",
            storeId,
            productId,
            ProductSerialsSetBody(numbers.map { ProductSerialWriteBody(it, variantId) }),
        )
    }
}
