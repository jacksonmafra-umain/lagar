package app.lagar.data

/** Read-only access to the static API. Failures (missing file, network) surface as exceptions. */
interface LagarRepository {
    suspend fun index(): ApiIndex

    /** [type] null lists the whole layer; pages are 1-based. */
    suspend fun listing(layer: String, type: String?, page: Int): ListingPage

    suspend fun document(id: String): DocumentResponse
}

/** The per-ministry indexes of the API (`<layer>/<type>/by-ministry/`); only SFS series have them. */
interface MinistryRepository {
    suspend fun ministries(layer: String, type: String): MinistryIndex

    /** One ministry's paged listing; pages are 1-based. */
    suspend fun ministryListing(layer: String, type: String, ministry: String, page: Int): ListingPage
}

/** The per-locality listings of the API (`<layer>/by-code/`): the region layer by län, the municipality layer by kommun. */
interface LocalityRepository {
    suspend fun localities(layer: String): LocalityIndex

    /** One county's or kommun's paged listing; pages are 1-based. */
    suspend fun localityListing(layer: String, code: String, page: Int): ListingPage
}

/**
 * Public services for the Tjänster tab and the reader, read once per process. An API without the service files
 * (built before the service layer) has no services: both functions then answer empty instead of failing. Other
 * failures surface as exceptions and are not cached.
 */
interface ServiceRepository {
    /** Every service, in listing order (slug ascending). */
    suspend fun serviceCatalog(): ServiceCatalog

    /** The services based on document [id], in catalogue order; empty when the norm has none. */
    suspend fun servicesForNorm(id: String): List<ServiceSummary>
}

/** The raw service files of the API (`service/catalog.json`, `service/by-norm/index.json`), before caching. */
interface ServiceSource {
    suspend fun serviceCatalog(): ServiceCatalog

    suspend fun serviceNormIndex(): ServiceNormIndex
}

/** A raw source of the whole API, before caching. */
interface ApiSource :
    LagarRepository,
    MinistryRepository,
    LocalityRepository,
    ServiceSource

internal fun indexPath() = "index.json"

internal fun listingPath(layer: String, type: String?, page: Int) =
    if (type == null) "$layer/index-$page.json" else "$layer/$type/index-$page.json"

internal fun documentPath(id: String) = "docs/$id.json"

internal fun ministryIndexPath(layer: String, type: String) = "$layer/$type/by-ministry/index.json"

internal fun ministryListingPath(layer: String, type: String, ministry: String, page: Int) =
    "$layer/$type/by-ministry/$ministry/index-$page.json"

internal fun localityIndexPath(layer: String) = "$layer/by-code/index.json"

internal fun localityListingPath(layer: String, code: String, page: Int) = "$layer/by-code/$code/index-$page.json"

internal fun serviceCatalogPath() = "service/catalog.json"

internal fun serviceNormIndexPath() = "service/by-norm/index.json"
