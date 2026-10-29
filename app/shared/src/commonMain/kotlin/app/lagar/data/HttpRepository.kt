package app.lagar.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.statement.HttpResponse
import io.ktor.http.isSuccess

/** Fetches the static API over HTTP; non-2xx responses and transport errors throw. */
class HttpRepository(
    private val client: HttpClient,
    baseUrl: String,
) : ApiSource {
    private val base = baseUrl.trimEnd('/') + "/"

    override suspend fun index(): ApiIndex = fetch(indexPath())

    override suspend fun listing(layer: String, type: String?, page: Int): ListingPage =
        fetch(listingPath(layer, type, page))

    override suspend fun document(id: String): DocumentResponse = fetch(documentPath(id))

    override suspend fun ministries(layer: String, type: String): MinistryIndex = fetch(ministryIndexPath(layer, type))

    override suspend fun ministryListing(layer: String, type: String, ministry: String, page: Int): ListingPage =
        fetch(ministryListingPath(layer, type, ministry, page))

    private suspend inline fun <reified T> fetch(path: String): T {
        val response: HttpResponse = client.get(base + path)
        if (!response.status.isSuccess()) {
            throw ApiException("GET $path failed: ${response.status}")
        }
        return response.body()
    }
}

class ApiException(message: String) : Exception(message)
