package app.lagar.data

import io.ktor.client.HttpClient
import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.respond
import io.ktor.client.engine.mock.respondError
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.http.headersOf
import io.ktor.serialization.kotlinx.json.json
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class HttpRepositoryTest {
    private val jsonHeaders = headersOf(HttpHeaders.ContentType, "application/json")

    private fun repo(engine: MockEngine) = HttpRepository(
        HttpClient(engine) {
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
        },
        baseUrl = "https://example.test/api/v1/",
    )

    @Test
    fun listingRequestsTypedPagePath() = runTest {
        val urls = mutableListOf<String>()
        val repository = repo(MockEngine { request ->
            urls += request.url.toString()
            respond(ApiExamples.actListing, headers = jsonHeaders)
        })
        val page = repository.listing("sfs", "act", 2)
        assertEquals(listOf("https://example.test/api/v1/sfs/act/index-2.json"), urls)
        assertEquals("act", page.type)
    }

    @Test
    fun layerListingOmitsTypeSegment() = runTest {
        val urls = mutableListOf<String>()
        val repository = repo(MockEngine { request ->
            urls += request.url.toString()
            respond(ApiExamples.sfsListing, headers = jsonHeaders)
        })
        repository.listing("sfs", null, 1)
        assertEquals(listOf("https://example.test/api/v1/sfs/index-1.json"), urls)
    }

    @Test
    fun indexAndDocumentPaths() = runTest {
        val urls = mutableListOf<String>()
        val repository = repo(MockEngine { request ->
            urls += request.url.toString()
            val body = if (request.url.encodedPath.endsWith("index.json")) ApiExamples.index else ApiExamples.document
            respond(body, headers = jsonHeaders)
        })
        repository.index()
        assertEquals("sfs-1999-175", repository.document("sfs-1999-175").meta.id)
        assertEquals(
            listOf("https://example.test/api/v1/index.json", "https://example.test/api/v1/docs/sfs-1999-175.json"),
            urls,
        )
    }

    @Test
    fun notFoundSurfacesAsException() = runTest {
        val repository = repo(MockEngine { respondError(HttpStatusCode.NotFound) })
        assertFailsWith<Exception> { repository.document("sfs-0000-0") }
    }

    @Test
    fun serverErrorSurfacesAsException() = runTest {
        val repository = repo(MockEngine { respondError(HttpStatusCode.InternalServerError) })
        assertFailsWith<Exception> { repository.index() }
    }

    @Test
    fun networkFailureSurfacesAsException() = runTest {
        val repository = repo(MockEngine { throw IllegalStateException("offline") })
        assertFailsWith<Exception> { repository.index() }
    }
}
