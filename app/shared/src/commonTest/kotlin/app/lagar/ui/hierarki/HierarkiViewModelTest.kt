package app.lagar.ui.hierarki

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.data.ListingPage
import app.lagar.data.ServiceCatalog
import app.lagar.data.ServiceRepository
import app.lagar.data.ServiceSummary
import app.lagar.domain.DisplayLayer
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
class HierarkiViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    private val index = ApiIndex(
        1,
        "2026-11-14T00:00:00Z",
        listOf(
            ApiLayer("sfs", 10, listOf(ApiSeries("act", 6), ApiSeries("ordinance", 4))),
            ApiLayer("service", 3, emptyList()),
        ),
    )

    private class FakeIndex(private val index: ApiIndex, var fail: Boolean = false) : LagarRepository {
        override suspend fun index(): ApiIndex {
            if (fail) error("offline")
            return index
        }

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage = error("not used")

        override suspend fun document(id: String): DocumentResponse = error("not used")
    }

    private class FakeServices(private val total: Int, var fail: Boolean = false) : ServiceRepository {
        override suspend fun serviceCatalog(): ServiceCatalog {
            if (fail) error("offline")
            return ServiceCatalog(total, emptyList())
        }

        override suspend fun servicesForNorm(id: String): List<ServiceSummary> = emptyList()
    }

    private fun LoadState<List<LayerSummary>>.count(layer: DisplayLayer): Int =
        assertIs<LoadState.Loaded<List<LayerSummary>>>(this).value.single { it.layer == layer }.count

    @Test
    fun theServiceLevelCountsTheCatalogue() {
        val vm = HierarkiViewModel(FakeIndex(index), FakeServices(total = 12))
        assertEquals(12, vm.state.value.count(DisplayLayer.Service))
        assertEquals(6, vm.state.value.count(DisplayLayer.SfsAct))
    }

    @Test
    fun aFailedCatalogueKeepsTheIndexCount() {
        val vm = HierarkiViewModel(FakeIndex(index), FakeServices(total = 12, fail = true))
        assertEquals(3, vm.state.value.count(DisplayLayer.Service))
    }

    @Test
    fun aFailedIndexFailsAndRetries() {
        val documents = FakeIndex(index, fail = true)
        val vm = HierarkiViewModel(documents, FakeServices(total = 12))
        val failed = assertIs<LoadState.Failed>(vm.state.value)
        documents.fail = false
        failed.retry()
        assertEquals(12, vm.state.value.count(DisplayLayer.Service))
    }

    @Test
    fun withServiceCountOnlyChangesTheServiceLevel() {
        val summaries = index.layerSummaries()
        val counted = summaries.withServiceCount(40)
        assertEquals(40, counted.single { it.layer == DisplayLayer.Service }.count)
        assertEquals(summaries.filter { it.layer != DisplayLayer.Service }, counted.filter { it.layer != DisplayLayer.Service })
    }
}
