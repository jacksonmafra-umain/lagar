package app.lagar.data

/** Read-only access to the static API. Failures (missing file, network) surface as exceptions. */
interface LagarRepository {
    suspend fun index(): ApiIndex

    /** [type] null lists the whole layer; pages are 1-based. */
    suspend fun listing(layer: String, type: String?, page: Int): ListingPage

    suspend fun document(id: String): DocumentResponse
}

internal fun indexPath() = "index.json"

internal fun listingPath(layer: String, type: String?, page: Int) =
    if (type == null) "$layer/index-$page.json" else "$layer/$type/index-$page.json"

internal fun documentPath(id: String) = "docs/$id.json"
