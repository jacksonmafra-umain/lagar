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
 * One listing entry. [inForce], [amendedThrough], [ministry], [regionCode] and [municipalityCode] were added within
 * API v1; they default to null so payloads built before them still decode. [regionCode] is the county (län) code of
 * county and municipal regulations, [municipalityCode] the kommun code of municipal regulations.
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
    @SerialName("region_code") val regionCode: String? = null,
    @SerialName("municipality_code") val municipalityCode: String? = null,
)

/** `<layer>/by-code/index.json`: the documents of a locality layer grouped by county or kommun code. */
@Serializable
data class LocalityIndex(
    val layer: String,
    val field: String,
    val total: Int,
    val codes: List<LocalityCount>,
) {
    /** Documents with [code]; 0 when the index does not list it. */
    fun count(code: String): Int = codes.firstOrNull { it.code == code }?.count ?: 0
}

/** One county or kommun [code] and the number of documents that carry it. */
@Serializable
data class LocalityCount(val code: String, val count: Int)

/** `<layer>/<type>/by-ministry/index.json`: the type's documents grouped by issuing ministry. */
@Serializable
data class MinistryIndex(
    val layer: String,
    val type: String,
    val total: Int,
    val unassigned: Int,
    val ministries: List<ApiMinistry>,
)

/** One issuing ministry: [id] names its listing folder, [name] is the ministry without a unit code. */
@Serializable
data class ApiMinistry(val id: String, val name: String, val count: Int)

/**
 * Document metadata. [amendments] was added within API v1 and is null until the statute has been read from the
 * SFS register; it and the other lists and dates default so that older payloads still decode.
 *
 * [basedOn] to [template] are the fields of a `public_service` (layer `service`), also added within v1; every other
 * type serves them as null, and payloads built before them leave them out.
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
    @SerialName("based_on") val basedOn: List<String>? = null,
    val audience: List<String>? = null,
    val topics: List<String>? = null,
    val channels: List<String>? = null,
    @SerialName("service_url") val serviceUrl: String? = null,
    @SerialName("issuer_org_number") val issuerOrgNumber: String? = null,
    val scope: String? = null,
    val template: Boolean? = null,
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

/** `service/catalog.json`: every public service, in listing order (slug ascending). */
@Serializable
data class ServiceCatalog(val total: Int, val services: List<ServiceSummary>) {
    companion object {
        /** The catalogue of an API without services. */
        val Empty = ServiceCatalog(0, emptyList())
    }
}

/**
 * One public service of the catalogue. [title] is Swedish as the responsible body publishes it. [audience] holds
 * `private` and/or `business`; [topics] the life-event topics; [channels] `online`, `form`, `phone` or `office`
 * (may be empty); [scope] is `national`, `region` or `municipality`. A [template] service is one every region or
 * kommun must offer, with both codes null. [serviceUrl] is where the service starts when it differs from [source].
 */
@Serializable
data class ServiceSummary(
    val id: String,
    val title: String,
    val issuer: String,
    val audience: List<String>,
    val topics: List<String>,
    val channels: List<String>,
    val scope: String,
    val template: Boolean,
    @SerialName("region_code") val regionCode: String? = null,
    @SerialName("municipality_code") val municipalityCode: String? = null,
    val source: String,
    @SerialName("service_url") val serviceUrl: String? = null,
    @SerialName("based_on") val basedOn: List<ServiceNormRef>,
)

/** A norm a service is based on, resolved to the values of its `meta`; [id] opens `docs/<id>.json`. */
@Serializable
data class ServiceNormRef(val id: String, val title: String, val type: String, val layer: String)

/** `service/by-norm/index.json`: document id to the ids of the services based on it, in catalogue order. */
@Serializable
data class ServiceNormIndex(val norms: Map<String, List<String>>) {
    /** The services based on document [id]; empty when the index does not list it. */
    fun serviceIds(id: String): List<String> = norms[id].orEmpty()
}
