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
        val repository = repo(
            MockEngine { request ->
                urls += request.url.toString()
                respond(ApiExamples.actListing, headers = jsonHeaders)
            },
        )
        val page = repository.listing("sfs", "act", 2)
        assertEquals(listOf("https://example.test/api/v1/sfs/act/index-2.json"), urls)
        assertEquals("act", page.type)
    }

    @Test
    fun layerListingOmitsTypeSegment() = runTest {
        val urls = mutableListOf<String>()
        val repository = repo(
            MockEngine { request ->
                urls += request.url.toString()
                respond(ApiExamples.sfsListing, headers = jsonHeaders)
            },
        )
        repository.listing("sfs", null, 1)
        assertEquals(listOf("https://example.test/api/v1/sfs/index-1.json"), urls)
    }

    @Test
    fun indexAndDocumentPaths() = runTest {
        val urls = mutableListOf<String>()
        val repository = repo(
            MockEngine { request ->
                urls += request.url.toString()
                val body = if (request.url.encodedPath.endsWith("index.json")) ApiExamples.index else ApiExamples.document
                respond(body, headers = jsonHeaders)
            },
        )
        repository.index()
        assertEquals("sfs-1999-175", repository.document("sfs-1999-175").meta.id)
        assertEquals(
            listOf("https://example.test/api/v1/index.json", "https://example.test/api/v1/docs/sfs-1999-175.json"),
            urls,
        )
    }

    @Test
    fun gzipDocumentsAreDecompressed() = runTest {
        val urls = mutableListOf<String>()
        val gzipIndex = ApiExamples.index.replace("\"docs_encoding\": \"json\"", "\"docs_encoding\": \"gzip\"")
        // Python: gzip.compress(ApiExamples.document, compresslevel=9, mtime=0), as api/build.py writes documents.
        val packed = listOf(
            31, -117, 8, 0, 0, 0, 0, 0, 2, 19, -115, 82, -53, -82, -45, 48, 16, -35, -9, 43, -84, -80, -127, -118,
            -76, 73, -38, -12, -75, 103, 113, 65, 108, -82, 88, 65, 81, 53, -119, -57, -119, 21, -41, -87, 60, -109,
            74, 21, -70, 127, 83, -60, 31, -16, 1, -12, -57, -80, -37, -122, 94, 40, -117, 43, 101, 49, 57, -57, -25,
            -52, -8, 120, 6, -33, 6, 66, 68, 91, 100, -120, 86, 34, -44, -2, 79, 75, 95, 71, -92, 40, 78, -105, -53,
            101, -100, -50, -13, -24, -19, -123, 97, -51, 6, 3, -7, 120, 58, 50, -109, -74, -86, 117, 91, 96, -35, 90,
            82, -89, -97, -82, 117, -46, 106, 91, -119, -41, 65, -73, -14, -70, 55, 127, -124, -121, -35, 89, -25, 79,
            104, 11, -74, -60, -98, 48, 112, 64, 119, 109, -41, 99, -74, -37, 22, 23, -80, -9, -23, 25, 77, -44, -95,
            -20, -103, 56, -103, -60, -39, -115, -77, 27, 63, 77, 25, -38, -40, -50, -104, 43, -22, 112, -121, 96,
            -50, -102, 103, 40, 108, -47, 74, -108, -101, -30, -32, -15, 47, 95, -1, 65, -71, 118, 109, 87, -43, -95,
            77, -106, 100, -77, -43, 34, 79, -93, -101, -99, -45, -106, -17, -92, 91, 109, 53, -79, 11, 88, -12, -66,
            35, -97, -109, 70, -119, 59, 112, -116, -34, -108, -111, -59, -121, -57, -121, -113, -67, 11, 26, -3, -9,
            60, 6, 108, -43, 65, 117, -114, -120, -10, -3, 49, -24, -72, 110, -99, 102, 31, -16, 62, 80, 10, 12, -31,
            -107, -93, -74, -69, -36, 53, -86, -103, 119, -76, 26, -113, 37, 48, -116, -100, 110, 72, 122, 35, 59, 34,
            28, -53, -74, -23, 66, -9, -15, -1, -98, -14, 98, -80, -95, 26, -78, 124, 22, 124, -106, 42, 43, 102, 101,
            42, -89, -72, -128, 121, 50, -55, -117, -76, -100, -55, 12, -105, 106, 10, -117, 73, 49, 79, -54, 92, -90,
            56, 83, 25, 44, -117, -59, -76, -100, -56, 57, 38, 42, -123, -84, -104, -108, 83, -103, 123, -94, 55, 86,
            -56, 101, -19, 3, 2, -18, 3, -116, -45, 36, -50, -26, -97, -46, 100, -107, -124, -17, 115, -12, 60, -17,
            48, 32, 93, -45, -16, -16, 83, -32, -94, -94, -107, -25, 40, 95, -119, -105, 46, -38, -38, -82, -19, 59,
            102, -47, 42, -27, 13, -115, -82, 88, -72, 59, 41, 29, -56, -65, 71, 56, 58, 28, -90, -30, -41, -113, -31,
            80, 60, 8, 58, 40, 70, 1, 94, -53, -38, -104, -32, 78, -89, 99, -29, 64, 72, -76, 55, 59, 16, -127, -39,
            -125, -31, -48, 56, 48, 101, 45, -48, 82, -93, -115, -124, -77, -78, 58, 125, -9, 19, -123, 74, 84, -82,
            -77, -46, -100, -114, 85, 5, 126, -95, -18, 7, 17, 90, -96, -63, -122, 93, -21, -73, -90, 17, 1, 23, -44,
            -128, 87, 74, -65, 41, 74, 91, 11, 36, -16, 101, -73, 25, -83, 109, 52, 120, 26, -4, 6, -83, -86, 103,
            124, -56, 3, 0, 0,
        ).map { it.toByte() }.toByteArray()
        val repository = repo(
            MockEngine { request ->
                urls += request.url.toString()
                if (request.url.encodedPath.endsWith("index.json")) {
                    respond(gzipIndex, headers = jsonHeaders)
                } else {
                    respond(packed, headers = headersOf(HttpHeaders.ContentType, "application/gzip"))
                }
            },
        )
        val plain = Json { ignoreUnknownKeys = true }.decodeFromString(DocumentResponse.serializer(), ApiExamples.document)
        assertEquals(plain, repository.document("sfs-1999-175"))
        assertEquals("sfs-1999-175", repository.document("sfs-1999-175").meta.id)
        assertEquals(
            listOf(
                "https://example.test/api/v1/index.json",
                "https://example.test/api/v1/docs/sfs-1999-175.json.gz",
                "https://example.test/api/v1/docs/sfs-1999-175.json.gz",
            ),
            urls,
        )
    }

    @Test
    fun ministryIndexAndListingPaths() = runTest {
        val urls = mutableListOf<String>()
        val repository = repo(
            MockEngine { request ->
                urls += request.url.toString()
                val body = if (request.url.encodedPath.endsWith("by-ministry/index.json")) {
                    ApiExamples.ordinanceMinistries
                } else {
                    ApiExamples.ordinanceMinistryListing
                }
                respond(body, headers = jsonHeaders)
            },
        )
        val index = repository.ministries("sfs", "ordinance")
        assertEquals(listOf(ApiMinistry("justitiedepartementet", "Justitiedepartementet", 1)), index.ministries)
        assertEquals(2 to 1, index.total to index.unassigned)
        val page = repository.ministryListing("sfs", "ordinance", "justitiedepartementet", 1)
        assertEquals(listOf("sfs-1999-175"), page.items.map { it.id })
        assertEquals(
            listOf(
                "https://example.test/api/v1/sfs/ordinance/by-ministry/index.json",
                "https://example.test/api/v1/sfs/ordinance/by-ministry/justitiedepartementet/index-1.json",
            ),
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
