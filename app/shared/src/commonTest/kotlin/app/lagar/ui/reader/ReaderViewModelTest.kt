package app.lagar.ui.reader

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.data.Catalog
import app.lagar.data.DocumentMeta
import app.lagar.data.DocumentResponse
import app.lagar.data.FakeSearchSource
import app.lagar.data.FullTextIndex
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.data.ListingPage
import app.lagar.data.ServiceCatalog
import app.lagar.data.ServiceNormRef
import app.lagar.data.ServiceRepository
import app.lagar.data.ServiceSummary
import app.lagar.domain.LoadState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

@OptIn(ExperimentalCoroutinesApi::class)
class ReaderViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private class FakeRepository(
        var failing: Boolean,
        val listed: List<String> = emptyList(),
        val body: String = "# Title",
        val types: Map<String, String> = emptyMap(),
    ) : LagarRepository {
        val requested = mutableListOf<String>()
        var listings = 0

        override suspend fun document(id: String): DocumentResponse {
            requested += id
            if (failing) throw IllegalStateException("boom")
            return DocumentResponse(
                DocumentMeta(
                    id, "Title", "act", "sfs", "1:1", null, null, null, emptyList(), null, emptyList(),
                    null, null, "sv", false, "https://example.org", "", "",
                ),
                body,
            )
        }

        override suspend fun index(): ApiIndex = ApiIndex(1, "t", listOf(ApiLayer("sfs", listed.size, listOf(ApiSeries("act", listed.size)))))

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            listings++
            if (failing) throw IllegalStateException("boom")
            val items = listed.map { ListingItem(it, "Title", "1:1", types[it] ?: "act", null, null) }
            return ListingPage(layer, type, 1, 1, items.size, items)
        }
    }

    /** Services by norm id; [failing] makes every lookup throw, as an unreachable API would. */
    private class FakeServices(val byNorm: Map<String, List<ServiceSummary>> = emptyMap(), val failing: Boolean = false) : ServiceRepository {
        val requested = mutableListOf<String>()

        override suspend fun serviceCatalog(): ServiceCatalog = ServiceCatalog(0, emptyList())

        override suspend fun servicesForNorm(id: String): List<ServiceSummary> {
            requested += id
            if (failing) throw IllegalStateException("boom")
            return byNorm[id].orEmpty()
        }
    }

    private fun service(id: String, norm: String) = ServiceSummary(
        id = id,
        title = "Ansök om $id",
        issuer = "Försäkringskassan",
        audience = listOf("private"),
        topics = listOf("family"),
        channels = listOf("online"),
        scope = "national",
        template = false,
        source = "https://example.org/$id",
        basedOn = listOf(ServiceNormRef(norm, "Title", "act", "sfs")),
    )

    private fun viewModel(
        repo: FakeRepository,
        id: String = "doc-1",
        index: FullTextIndex? = null,
        services: ServiceRepository? = null,
    ) = ReaderViewModel(repo, Catalog(repo), id, index, Dispatchers.Main, services)

    @Test
    fun loadsTheDocument() {
        val vm = viewModel(FakeRepository(failing = false))
        val loaded = assertIs<LoadState.Loaded<*>>(vm.state.value)
        assertEquals("# Title", (loaded.value as DocumentResponse).body)
    }

    @Test
    fun failureOffersRetryThatReloads() {
        val repo = FakeRepository(failing = true)
        val vm = viewModel(repo)
        val failed = assertIs<LoadState.Failed>(vm.state.value)
        repo.failing = false
        failed.retry()
        assertIs<LoadState.Loaded<*>>(vm.state.value)
        assertEquals(listOf("doc-1", "doc-1"), repo.requested)
    }

    @Test
    fun linksOnlyTheAmendmentsTheApiPublishes() {
        val repo = FakeRepository(failing = false, listed = listOf("sfs-1983-240", "sfs-1962-700", "sfs-n2019-2"))
        val vm = viewModel(repo, id = "sfs-1962-700")
        vm.resolveAmendmentLinks(listOf("1970:225", "1983:240", "1962:700", "N2019:2", "not a number"))
        assertEquals(mapOf("1983:240" to "sfs-1983-240", "N2019:2" to "sfs-n2019-2"), vm.linkedAmendments.value)
        vm.resolveAmendmentLinks(listOf("1983:240"))
        assertEquals(1, repo.listings)
    }

    @Test
    fun aFailedLookupLeavesPlainNumbersAndCanRetry() {
        val repo = FakeRepository(failing = false, listed = listOf("sfs-1983-240"))
        val vm = viewModel(repo)
        repo.failing = true
        vm.resolveAmendmentLinks(listOf("1983:240"))
        assertEquals(emptyMap(), vm.linkedAmendments.value)
        repo.failing = false
        vm.resolveAmendmentLinks(listOf("1983:240"))
        assertEquals(mapOf("1983:240" to "sfs-1983-240"), vm.linkedAmendments.value)
    }

    @Test
    fun resolvesTheCitedDocumentsTheApiPublishes() {
        val repo = FakeRepository(
            failing = false,
            listed = listOf("sfs-1962-700", "sfs-1974-152", "nja-2026-38"),
            body = "**1 §** Se brottsbalken (1962:700), regeringsformen (1974:152), NJA 2026:38 och lagen (1999:1).",
            types = mapOf("sfs-1974-152" to "fundamental_law", "nja-2026-38" to "case_report"),
        )
        val vm = viewModel(repo, id = "sfs-1962-700")
        assertEquals(mapOf("sfs-1974-152" to "fundamental_law", "nja-2026-38" to "case_report"), vm.crossReferences.value)
    }

    @Test
    fun aBodyWithoutCitationsSkipsTheCatalog() {
        val repo = FakeRepository(failing = false, listed = listOf("sfs-1962-700"), body = "**1 §** Enligt 2 kap. 3 § gäller detta.")
        val vm = viewModel(repo)
        assertEquals(emptyMap(), vm.crossReferences.value)
        assertEquals(0, repo.listings)
    }

    @Test
    fun checksCitationsAgainstTheSearchIndexWithoutTheCatalog() {
        val repo = FakeRepository(failing = false, body = "Se skollagen (2010:800) och lagen (1999:1).")
        val source = FakeSearchSource()
        val vm = viewModel(repo, index = FullTextIndex(source))
        assertEquals(mapOf("sfs-2010-800" to "act"), vm.crossReferences.value)
        assertEquals(listOf<String?>("fundamental", "sfs"), source.docsRequests)
        assertEquals(0, repo.listings)
    }

    @Test
    fun fallsBackToTheCatalogWhenTheApiHasNoIndex() {
        val repo = FakeRepository(failing = false, listed = listOf("sfs-2010-800"), body = "Se skollagen (2010:800).")
        val vm = viewModel(repo, index = FullTextIndex(FakeSearchSource(missing = true)))
        assertEquals(mapOf("sfs-2010-800" to "act"), vm.crossReferences.value)
        assertEquals(1, repo.listings)
    }

    @Test
    fun listsTheServicesBasedOnTheDocument() {
        val based = listOf(service("service-foraldrapenning", "sfs-2010-110"), service("service-barnbidrag", "sfs-2010-110"))
        val services = FakeServices(mapOf("sfs-2010-110" to based))
        val vm = viewModel(FakeRepository(failing = false), id = "sfs-2010-110", services = services)
        assertEquals(based, vm.services.value)
        assertEquals(listOf("sfs-2010-110"), services.requested)
    }

    @Test
    fun aDocumentWithoutServicesHasNone() {
        val services = FakeServices(mapOf("sfs-2010-110" to listOf(service("service-foraldrapenning", "sfs-2010-110"))))
        val vm = viewModel(FakeRepository(failing = false), id = "sfs-1962-700", services = services)
        assertEquals(emptyList(), vm.services.value)
    }

    @Test
    fun aFailingServiceLookupLeavesTheReaderWorking() {
        val vm = viewModel(FakeRepository(failing = false), services = FakeServices(failing = true))
        assertEquals(emptyList(), vm.services.value)
        val loaded = assertIs<LoadState.Loaded<*>>(vm.state.value)
        assertEquals("# Title", (loaded.value as DocumentResponse).body)
    }
}
