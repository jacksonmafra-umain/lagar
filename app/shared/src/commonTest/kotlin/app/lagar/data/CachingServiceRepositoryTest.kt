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
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class CachingServiceRepositoryTest {
    private val json = Json { ignoreUnknownKeys = true }
    private val catalog = json.decodeFromString<ServiceCatalog>(ApiExamples.serviceCatalog)
    private val index = json.decodeFromString<ServiceNormIndex>(ApiExamples.serviceByNorm)

    private inner class FakeSource(
        var catalogResult: suspend () -> ServiceCatalog = { catalog },
        var indexResult: suspend () -> ServiceNormIndex = { index },
    ) : ServiceSource {
        var catalogCalls = 0
        var indexCalls = 0

        override suspend fun serviceCatalog(): ServiceCatalog {
            catalogCalls++
            return catalogResult()
        }

        override suspend fun serviceNormIndex(): ServiceNormIndex {
            indexCalls++
            return indexResult()
        }
    }

    private fun ids(services: List<ServiceSummary>) = services.map { it.id }

    @Test
    fun normWithServicesListsThemInCatalogueOrder() = runTest {
        val repo = CachingServiceRepository(FakeSource())
        val services = repo.servicesForNorm("sfs-2010-800")
        assertEquals(listOf("service-forskola", "service-registerutdrag-skola-forskola"), ids(services))
        assertEquals(listOf(catalog.services[1], catalog.services[2]), services)
        assertEquals(listOf("service-adoptionsbidrag"), ids(repo.servicesForNorm("sfs-2010-110")))
    }

    @Test
    fun normWithoutServicesIsEmptyWithoutReadingTheCatalogue() = runTest {
        val source = FakeSource()
        val repo = CachingServiceRepository(source)
        assertEquals(emptyList(), repo.servicesForNorm("sfs-1999-175"))
        assertEquals(0, source.catalogCalls)
    }

    @Test
    fun missingByNormFileMeansNoServicesAndIsNotFetchedAgain() = runTest {
        val source = FakeSource(indexResult = { throw ApiException("missing", 404) })
        val repo = CachingServiceRepository(source)
        assertEquals(emptyList(), repo.servicesForNorm("sfs-2010-800"))
        assertEquals(emptyList(), repo.servicesForNorm("sfs-2010-110"))
        assertEquals(1, source.indexCalls)
        assertEquals(0, source.catalogCalls)
    }

    @Test
    fun missingCatalogueIsEmpty() = runTest {
        val source = FakeSource(catalogResult = { throw ApiException("missing", 404) })
        val repo = CachingServiceRepository(source)
        assertEquals(ServiceCatalog.Empty, repo.serviceCatalog())
        assertEquals(emptyList(), repo.servicesForNorm("sfs-2010-800"))
        assertEquals(1, source.catalogCalls)
    }

    @Test
    fun idMissingFromTheCatalogueIsSkipped() = runTest {
        val source = FakeSource(indexResult = { ServiceNormIndex(mapOf("sfs-1-1" to listOf("service-x", catalog.services[0].id))) })
        val repo = CachingServiceRepository(source)
        assertEquals(listOf("service-adoptionsbidrag"), ids(repo.servicesForNorm("sfs-1-1")))
    }

    @Test
    fun catalogueAndIndexAreFetchedOncePerSession() = runTest {
        val source = FakeSource()
        val repo = CachingServiceRepository(source)
        assertSame(catalog, repo.serviceCatalog())
        assertSame(catalog, repo.serviceCatalog())
        repo.servicesForNorm("sfs-2010-800")
        repo.servicesForNorm("sfs-1998-620")
        repo.servicesForNorm("sfs-1999-175")
        assertEquals(1, source.catalogCalls)
        assertEquals(1, source.indexCalls)
    }

    @Test
    fun otherFailuresSurfaceAndAreNotCached() = runTest {
        val source = FakeSource(
            catalogResult = { throw ApiException("server error", 500) },
            indexResult = { throw IllegalStateException("offline") },
        )
        val repo = CachingServiceRepository(source)
        assertFailsWith<ApiException> { repo.serviceCatalog() }
        assertFailsWith<IllegalStateException> { repo.servicesForNorm("sfs-2010-800") }
        source.catalogResult = { catalog }
        source.indexResult = { index }
        assertSame(catalog, repo.serviceCatalog())
        assertEquals(2, ids(repo.servicesForNorm("sfs-2010-800")).size)
        assertEquals(2, source.catalogCalls)
        assertEquals(2, source.indexCalls)
    }

    @Test
    fun concurrentCallersFetchOnce() = runTest {
        val gate = CompletableDeferred<Unit>()
        val source = FakeSource(
            catalogResult = {
                gate.await()
                catalog
            },
            indexResult = {
                gate.await()
                index
            },
        )
        val repo = CachingServiceRepository(source)
        val catalogs = List(3) { async { repo.serviceCatalog() } }
        val norms = List(3) { async { repo.servicesForNorm("sfs-2010-800") } }
        gate.complete(Unit)
        assertEquals(List(3) { catalog }, catalogs.awaitAll())
        assertEquals(List(3) { listOf(catalog.services[1], catalog.services[2]) }, norms.awaitAll())
        assertEquals(1, source.catalogCalls)
        assertEquals(1, source.indexCalls)
    }

    @Test
    fun overHttpAMissingByNormFileMeansNoServices() = runTest {
        val headers = headersOf(HttpHeaders.ContentType, "application/json")
        val engine = MockEngine { request ->
            if (request.url.encodedPath.endsWith("catalog.json")) {
                respond(ApiExamples.serviceCatalog, headers = headers)
            } else {
                respondError(HttpStatusCode.NotFound)
            }
        }
        val http = HttpRepository(
            HttpClient(engine) { install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) } },
            baseUrl = "https://example.test/api/v1/",
        )
        val repo = CachingServiceRepository(http)
        assertEquals(emptyList(), repo.servicesForNorm("sfs-2010-800"))
        assertEquals(3, repo.serviceCatalog().total)
    }
}
