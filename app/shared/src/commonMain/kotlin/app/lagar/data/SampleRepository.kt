package app.lagar.data

import app.lagar.resources.Res
import kotlinx.serialization.json.Json

/** Serves the API subset bundled under `files/sample/api/v1/`. */
class SampleRepository(
    private val readBytes: suspend (path: String) -> ByteArray = { Res.readBytes(it) },
) : ApiSource,
    SearchIndexSource {
    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun index() = read<ApiIndex>(indexPath())

    override suspend fun listing(layer: String, type: String?, page: Int) =
        read<ListingPage>(listingPath(layer, type, page))

    override suspend fun document(id: String) = read<DocumentResponse>(documentPath(id))

    override suspend fun ministries(layer: String, type: String) = read<MinistryIndex>(ministryIndexPath(layer, type))

    override suspend fun ministryListing(layer: String, type: String, ministry: String, page: Int) =
        read<ListingPage>(ministryListingPath(layer, type, ministry, page))

    override suspend fun localities(layer: String) = read<LocalityIndex>(localityIndexPath(layer))

    override suspend fun localityListing(layer: String, code: String, page: Int) =
        read<ListingPage>(localityListingPath(layer, code, page))

    override suspend fun searchManifest() = read<SearchManifest>(searchManifestPath())

    override suspend fun searchGroupManifest(group: String) = read<SearchGroupManifest>(searchGroupManifestPath(group))

    override suspend fun searchDocs(group: String?) = read<SearchDocsTable>(searchDocsPath(group))

    override suspend fun searchShard(group: String?, key: String) = read<SearchShard>(searchShardPath(group, key))

    private suspend inline fun <reified T> read(path: String): T =
        json.decodeFromString(readBytes("files/sample/api/v1/$path").decodeToString())
}
