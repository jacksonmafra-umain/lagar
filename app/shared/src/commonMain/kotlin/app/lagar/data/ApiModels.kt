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

/**
 * One listing entry. [inForce], [amendedThrough] and [ministry] were added within API v1; they default to null
 * so payloads built before them still decode.
 */
@Serializable
data class ListingItem(
    val id: String,
    val title: String,
    val number: String,
    val type: String,
    val issued: String?,
    val repealed: String?,
    @SerialName("in_force") val inForce: String? = null,
    @SerialName("amended_through") val amendedThrough: String? = null,
    val ministry: String? = null,
)

/**
 * Document metadata. [amendments] was added within API v1 and is null until the statute has been read from the
 * SFS register; it and the other lists and dates default so that older payloads still decode.
 */
@Serializable
data class DocumentMeta(
    val id: String,
    val title: String,
    val type: String,
    val layer: String,
    val number: String,
    val issued: String?,
    @SerialName("in_force") val inForce: String? = null,
    val repealed: String?,
    @SerialName("amended_by") val amendedBy: List<String> = emptyList(),
    @SerialName("amended_through") val amendedThrough: String? = null,
    @SerialName("reprinted_by") val reprintedBy: List<String> = emptyList(),
    val ministry: String?,
    val eli: String?,
    val language: String,
    val authoritative: Boolean,
    val source: String,
    @SerialName("source_sha256") val sourceSha256: String,
    @SerialName("fetched_at") val fetchedAt: String,
    val amendments: List<Amendment>? = null,
)

/** One amending act from the SFS register, in register order. Only [number] is always set. */
@Serializable
data class Amendment(
    val number: String,
    val title: String? = null,
    val scope: String? = null,
    @SerialName("preparatory_works") val preparatoryWorks: String? = null,
    val celex: String? = null,
    @SerialName("in_force") val inForce: String? = null,
    @SerialName("in_force_raw") val inForceRaw: String? = null,
)

@Serializable
data class DocumentResponse(val meta: DocumentMeta, val body: String)
