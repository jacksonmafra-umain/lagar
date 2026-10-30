package app.lagar.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.statement.HttpResponse
import io.ktor.http.isSuccess
import kotlinx.serialization.json.Json

/**
 * Fetches the static API over HTTP; non-2xx responses and transport errors throw. Documents are read as the API's
 * `docs_encoding` says (docs/api.md): plain JSON, or gzip files that are decompressed here.
 */
class HttpRepository(
    private val client: HttpClient,
    baseUrl: String,
) : ApiSource,
    SearchIndexSource {
    private val base = baseUrl.trimEnd('/') + "/"
    private var docsEncoding: String? = null

    override suspend fun index(): ApiIndex = fetch<ApiIndex>(indexPath()).also { docsEncoding = it.docsEncoding }

    override suspend fun listing(layer: String, type: String?, page: Int): ListingPage =
        fetch(listingPath(layer, type, page))

    override suspend fun document(id: String): DocumentResponse {
        val encoding = docsEncoding ?: index().docsEncoding.also { docsEncoding = it }
        if (encoding != DOCS_GZIP) return fetch(documentPath(id))
        val text = Gzip.decompress(fetch<ByteArray>(gzipDocumentPath(id))).decodeToString()
        return DocumentJson.decodeFromString(DocumentResponse.serializer(), text)
    }

    override suspend fun ministries(layer: String, type: String): MinistryIndex = fetch(ministryIndexPath(layer, type))

    override suspend fun ministryListing(layer: String, type: String, ministry: String, page: Int): ListingPage =
        fetch(ministryListingPath(layer, type, ministry, page))

    override suspend fun localities(layer: String): LocalityIndex = fetch(localityIndexPath(layer))

    override suspend fun localityListing(layer: String, code: String, page: Int): ListingPage =
        fetch(localityListingPath(layer, code, page))

    override suspend fun searchManifest(): SearchManifest = fetch(searchManifestPath())

    override suspend fun searchGroupManifest(group: String): SearchGroupManifest = fetch(searchGroupManifestPath(group))

    override suspend fun searchDocs(group: String?): SearchDocsTable = fetch(searchDocsPath(group))

    override suspend fun searchShard(group: String?, key: String): SearchShard = fetch(searchShardPath(group, key))

    private suspend inline fun <reified T> fetch(path: String): T {
        val response: HttpResponse = client.get(base + path)
        if (!response.status.isSuccess()) {
            throw ApiException("GET $path failed: ${response.status}", response.status.value)
        }
        return response.body()
    }
}

private val DocumentJson = Json { ignoreUnknownKeys = true }

/** A failed API request; [status] is the HTTP status when the server answered. */
class ApiException(message: String, val status: Int? = null) : Exception(message) {
    val notFound: Boolean get() = status == HTTP_NOT_FOUND

    private companion object {
        const val HTTP_NOT_FOUND = 404
    }
}
