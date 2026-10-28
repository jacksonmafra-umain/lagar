package app.lagar.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ApiIndex(
    @SerialName("api_version") val apiVersion: Int,
    @SerialName("built_at") val builtAt: String,
    val layers: List<ApiLayer>,
)

@Serializable
data class ApiLayer(val id: String, val count: Int, val series: List<ApiSeries>)

@Serializable
data class ApiSeries(val id: String, val count: Int)

@Serializable
data class ListingPage(
    val layer: String,
    val type: String?,
    val page: Int,
    @SerialName("page_count") val pageCount: Int,
    val total: Int,
    val items: List<ListingItem>,
)

@Serializable
data class ListingItem(
    val id: String,
    val title: String,
    val number: String,
    val type: String,
    val issued: String?,
    val repealed: String?,
)

@Serializable
data class DocumentMeta(
    val id: String,
    val title: String,
    val type: String,
    val layer: String,
    val number: String,
    val issued: String?,
    @SerialName("in_force") val inForce: String?,
    val repealed: String?,
    @SerialName("amended_by") val amendedBy: List<String>,
    @SerialName("amended_through") val amendedThrough: String?,
    @SerialName("reprinted_by") val reprintedBy: List<String>,
    val ministry: String?,
    val eli: String?,
    val language: String,
    val authoritative: Boolean,
    val source: String,
    @SerialName("source_sha256") val sourceSha256: String,
    @SerialName("fetched_at") val fetchedAt: String,
)

@Serializable
data class DocumentResponse(val meta: DocumentMeta, val body: String)
