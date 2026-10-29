package app.lagar.data

import app.lagar.resources.Res
import kotlinx.serialization.json.Json

/** Serves the API subset bundled under `files/sample/api/v1/`. */
class SampleRepository(
    private val readBytes: suspend (path: String) -> ByteArray = { Res.readBytes(it) },
) : ApiSource {
    private val json = Json { ignoreUnknownKeys = true }

    override suspend fun index() = read<ApiIndex>(indexPath())

    override suspend fun listing(layer: String, type: String?, page: Int) =
        read<ListingPage>(listingPath(layer, type, page))

    override suspend fun document(id: String) = read<DocumentResponse>(documentPath(id))

    override suspend fun ministries(layer: String, type: String) = read<MinistryIndex>(ministryIndexPath(layer, type))

    override suspend fun ministryListing(layer: String, type: String, ministry: String, page: Int) =
        read<ListingPage>(ministryListingPath(layer, type, ministry, page))

    private suspend inline fun <reified T> read(path: String): T =
        json.decodeFromString(readBytes("files/sample/api/v1/$path").decodeToString())
}
