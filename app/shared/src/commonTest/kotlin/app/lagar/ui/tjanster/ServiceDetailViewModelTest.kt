package app.lagar.ui.tjanster

import app.lagar.data.ApiExamples
import app.lagar.data.ApiIndex
import app.lagar.data.DocumentResponse
import app.lagar.data.GeoRepository
import app.lagar.data.LagarRepository
import app.lagar.data.ListingPage
import app.lagar.data.ServiceCatalog
import app.lagar.data.ServiceRepository
import app.lagar.data.ServiceSummary
import app.lagar.domain.LoadState
import app.lagar.domain.Locality
import app.lagar.settings.UserPreferences
import com.russhwolf.settings.MapSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.json.Json
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

@OptIn(ExperimentalCoroutinesApi::class)
class ServiceDetailViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private val json = Json { ignoreUnknownKeys = true }
    private val catalog = json.decodeFromString<ServiceCatalog>(ApiExamples.serviceCatalog)
    private val document = json.decodeFromString<DocumentResponse>(ApiExamples.serviceDocument).copy(
        body = "# Registerutdrag för skola och förskola\n\nDu som ska arbeta i skolan behöver visa ett utdrag.\n\n" +
            "Källa: [Polismyndigheten](https://polisen.se/)\n",
    )

    private val geo = GeoRepository {
        """
        {"regions": [{"code": "01", "name": "Stockholms län"}],
         "kommuner": [{"code": "0180", "name": "Stockholm", "regionCode": "01", "website": "https://start.stockholm/"}]}
        """.encodeToByteArray()
    }

    private fun viewModel(
        services: ServiceRepository = FakeServices(catalog),
        documents: LagarRepository = FakeDocuments(document),
        preferences: UserPreferences = UserPreferences(MapSettings()),
        id: String = "service-registerutdrag-skola-forskola",
    ) = ServiceDetailViewModel(services, documents, preferences, geo, id)

    private class FakeServices(private val catalog: ServiceCatalog) : ServiceRepository {
        override suspend fun serviceCatalog() = catalog

        override suspend fun servicesForNorm(id: String): List<ServiceSummary> = emptyList()
    }

    private class FakeDocuments(private val document: DocumentResponse, var fail: Boolean = false) : LagarRepository {
        override suspend fun index(): ApiIndex = error("not used")

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage = error("not used")

        override suspend fun document(id: String): DocumentResponse {
            if (fail || id != document.meta.id) error("not found: $id")
            return document
        }
    }

    @Test
    fun combinesTheCatalogueEntryWithTheLeadAndFetchDate() {
        val viewModel = viewModel()
        val detail = assertIs<LoadState.Loaded<ServiceDetail>>(viewModel.state.value).value
        assertEquals("Polismyndigheten", detail.service.issuer)
        assertEquals(listOf("sfs-1998-620", "sfs-2010-800"), detail.service.basedOn.map { it.id })
        assertEquals("Du som ska arbeta i skolan behöver visa ett utdrag.", detail.lead)
        assertEquals("2026-11-13", detail.fetchedOn)
        assertEquals(ServicePlace.National, detail.place)
    }

    @Test
    fun aKommunTemplateCarriesTheChosenKommunAndItsWebsite() {
        val preferences = UserPreferences(MapSettings()).apply { setLocality(Locality("01", "0180")) }
        val forskola = document.copy(meta = document.meta.copy(id = "service-forskola"))
        val viewModel = viewModel(documents = FakeDocuments(forskola), preferences = preferences, id = "service-forskola")
        val detail = assertIs<LoadState.Loaded<ServiceDetail>>(viewModel.state.value).value
        assertEquals(ServicePlace.Kommun("Stockholm", "https://start.stockholm/"), detail.place)
    }

    @Test
    fun aServiceMissingFromTheCatalogueFails() {
        val viewModel = viewModel(services = FakeServices(ServiceCatalog.Empty))
        assertIs<LoadState.Failed>(viewModel.state.value)
    }

    @Test
    fun aFailedDocumentReadFailsAndRetries() {
        val documents = FakeDocuments(document, fail = true)
        val viewModel = viewModel(documents = documents)
        val failed = assertIs<LoadState.Failed>(viewModel.state.value)
        documents.fail = false
        failed.retry()
        assertIs<LoadState.Loaded<ServiceDetail>>(viewModel.state.value)
    }
}
