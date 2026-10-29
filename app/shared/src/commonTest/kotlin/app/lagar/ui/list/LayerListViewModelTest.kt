package app.lagar.ui.list

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.data.ListingPage
import app.lagar.data.MinistryIndex
import app.lagar.data.MinistryRepository
import app.lagar.domain.LoadState
import kotlinx.coroutines.CompletableDeferred
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
class LayerListViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    /** Serves 2 pages of 2 items; a page can be made to wait on a gate or to fail. */
    private class FakeRepository(private val pageCount: Int = 2) : LagarRepository {
        val calls = mutableListOf<Int>()
        val gates = mutableMapOf<Int, CompletableDeferred<Unit>>()
        val failing = mutableSetOf<Int>()
        var overlapOnLaterPages = false
        val listedTypes = mutableListOf<String?>()
        var indexFails = false
        var layers = listOf(
            ApiLayer("sfs", 6, listOf(ApiSeries("act", 4), ApiSeries("ordinance", 2))),
            ApiLayer("fundamental", 4, listOf(ApiSeries("fundamental_law", 4))),
            ApiLayer("eu", 0, emptyList()),
        )
        var emptyListing = false

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            calls += page
            listedTypes += type
            gates[page]?.await()
            if (page in failing) throw IllegalStateException("boom")
            if (emptyListing) return ListingPage(layer, type, 1, 1, total = 0, items = emptyList())
            return ListingPage(
                layer, type, page, pageCount, total = pageCount * 2,
                items = listOf(
                    ListingItem(if (overlapOnLaterPages && page > 1) "id-${page - 1}-b" else "id-$page-a", "A$page", "$page:1", "act", null, null),
                    ListingItem("id-$page-b", "B$page", "$page:2", "act", null, null),
                ),
            )
        }

        override suspend fun index(): ApiIndex {
            if (indexFails) throw IllegalStateException("offline")
            return ApiIndex(1, "2026-01-01T00:00:00Z", layers)
        }

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    /** Serves [pageCount] pages of one item for any ministry and records the requests. */
    private class FakeMinistries(private val pageCount: Int = 2) : MinistryRepository {
        val requests = mutableListOf<String>()

        override suspend fun ministries(layer: String, type: String): MinistryIndex = error("unused")

        override suspend fun ministryListing(layer: String, type: String, ministry: String, page: Int): ListingPage {
            requests += "$layer/$type/$ministry/$page"
            return ListingPage(
                layer, type, page, pageCount, total = pageCount,
                items = listOf(ListingItem("$ministry-$page", "T$page", "$page:1", type, null, null, ministry = ministry)),
            )
        }
    }

    @Test
    fun ministryFilterPagesThroughTheMinistryListing() {
        val repo = FakeRepository()
        val ministries = FakeMinistries()
        val vm = LayerListViewModel(repo, "sfs", "act", MinistryFilter("justitiedepartementet", "Justitiedepartementet"), ministries)
        vm.loadNext()
        vm.loadNext()
        assertEquals(listOf("sfs/act/justitiedepartementet/1", "sfs/act/justitiedepartementet/2"), ministries.requests)
        assertEquals(listOf("justitiedepartementet-1", "justitiedepartementet-2"), vm.items.value.map { it.id })
        assertEquals(2, vm.total.value)
        // Neither the layer listing nor the index is read, so the series switch stays hidden.
        assertEquals(emptyList(), repo.calls)
        assertEquals(emptyList(), vm.series.value)
    }

    @Test
    fun ministryFilterIgnoresSeriesSwitch() {
        val ministries = FakeMinistries(pageCount = 1)
        val vm = LayerListViewModel(FakeRepository(), "sfs", "act", MinistryFilter("riksbanken", "Riksbanken"), ministries)
        vm.selectSeries("ordinance")
        assertEquals("act", vm.selectedType.value)
        assertEquals(listOf("sfs/act/riksbanken/1"), ministries.requests)
    }

    @Test
    fun loadsFirstPageOnCreation() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        assertEquals(listOf(1), repo.calls)
        assertEquals(listOf("id-1-a", "id-1-b"), vm.items.value.map { it.id })
        assertEquals(4, vm.total.value)
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
    }

    @Test
    fun loadNextAppendsPageTwoAndStopsAtPageCount() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        vm.loadNext()
        assertEquals(listOf("id-1-a", "id-1-b", "id-2-a", "id-2-b"), vm.items.value.map { it.id })
        vm.loadNext()
        vm.loadNext()
        assertEquals(listOf(1, 2), repo.calls)
    }

    @Test
    fun loadNextDropsItemsWhoseIdIsAlreadyListed() {
        val repo = FakeRepository()
        repo.overlapOnLaterPages = true
        val vm = LayerListViewModel(repo, "sfs", "act")
        vm.loadNext()
        assertEquals(listOf("id-1-a", "id-1-b", "id-2-b"), vm.items.value.map { it.id })
    }

    @Test
    fun loadNextIsIdempotentWhileAPageLoads() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        repo.gates[2] = CompletableDeferred()
        vm.loadNext()
        vm.loadNext()
        vm.loadNext()
        assertEquals(listOf(1, 2), repo.calls)
        assertEquals(true, vm.appending.value)
        repo.gates.getValue(2).complete(Unit)
        assertEquals(4, vm.items.value.size)
        assertEquals(false, vm.appending.value)
    }

    @Test
    fun firstPageFailureIsFullScreenAndRetryReloads() {
        val repo = FakeRepository()
        repo.failing += 1
        val vm = LayerListViewModel(repo, "sfs", "act")
        val failed = assertIs<LoadState.Failed>(vm.state.value)
        repo.failing.clear()
        failed.retry()
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
        assertEquals(2, vm.items.value.size)
        assertEquals(listOf(1, 1), repo.calls)
    }

    @Test
    fun laterPageFailureKeepsItemsAndRetryAppends() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        repo.failing += 2
        vm.loadNext()
        assertEquals(true, vm.appendFailed.value)
        assertEquals(2, vm.items.value.size)
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
        // Scrolling must not retry a failed page on its own.
        vm.loadNext()
        assertEquals(listOf(1, 2), repo.calls)

        repo.failing.clear()
        vm.retryNext()
        assertEquals(false, vm.appendFailed.value)
        assertEquals(4, vm.items.value.size)
        assertEquals(listOf(1, 2, 2), repo.calls)
    }

    @Test
    fun loadNextWaitsForTheFirstPage() {
        val repo = FakeRepository()
        repo.gates[1] = CompletableDeferred()
        val vm = LayerListViewModel(repo, "sfs", "act")
        vm.loadNext()
        assertEquals(listOf(1), repo.calls)
        assertEquals(LoadState.Loading, vm.state.value)
    }

    @Test
    fun seriesComeFromTheIndexWhenTheLayerHasSeveral() {
        val vm = LayerListViewModel(FakeRepository(), "sfs", "act")
        assertEquals(listOf("act", "ordinance"), vm.series.value)
        assertEquals("act", vm.selectedType.value)
    }

    @Test
    fun aSingleSeriesOffersNoSwitch() {
        val vm = LayerListViewModel(FakeRepository(), "fundamental", null)
        assertEquals(0, vm.series.value.size)
    }

    @Test
    fun indexFailureHidesTheSwitchButStillLists() {
        val repo = FakeRepository()
        repo.indexFails = true
        val vm = LayerListViewModel(repo, "sfs", "act")
        assertEquals(0, vm.series.value.size)
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
        assertEquals(2, vm.items.value.size)
    }

    @Test
    fun selectSeriesReloadsFromPageOneOfThatSeries() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        vm.loadNext()
        assertEquals(4, vm.items.value.size)

        vm.selectSeries("ordinance")
        assertEquals("ordinance", vm.selectedType.value)
        assertEquals(listOf<String?>("act", "act", "ordinance"), repo.listedTypes)
        assertEquals(listOf(1, 2, 1), repo.calls)
        assertEquals(listOf("id-1-a", "id-1-b"), vm.items.value.map { it.id })
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)

        vm.loadNext()
        assertEquals("ordinance", repo.listedTypes.last())
    }

    @Test
    fun selectSeriesNullListsTheWholeLayer() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        vm.selectSeries(null)
        assertEquals(null, vm.selectedType.value)
        assertEquals(listOf<String?>("act", null), repo.listedTypes)
    }

    @Test
    fun selectingTheCurrentSeriesDoesNotReload() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        vm.selectSeries("act")
        assertEquals(listOf(1), repo.calls)
    }

    @Test
    fun selectSeriesCancelsAPendingAppend() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "act")
        repo.gates[2] = CompletableDeferred()
        vm.loadNext()
        vm.selectSeries("ordinance")
        repo.gates.getValue(2).complete(Unit)
        assertEquals(listOf("id-1-a", "id-1-b"), vm.items.value.map { it.id })
        assertEquals(false, vm.appending.value)
    }

    @Test
    fun anEmptyListingIsLoadedWithNoItems() {
        val repo = FakeRepository()
        repo.emptyListing = true
        repo.indexFails = true
        val vm = LayerListViewModel(repo, "eu", null)
        assertEquals(listOf(1), repo.calls)
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
        assertEquals(0, vm.items.value.size)
        assertEquals(0, vm.total.value)
    }

    @Test
    fun aSeriesMissingFromTheIndexIsEmptyWithoutFetching() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "sfs", "other_statute")
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
        assertEquals(0, vm.items.value.size)
        assertEquals(0, vm.total.value)
        assertEquals(0, repo.calls.size)
    }

    @Test
    fun aLayerTheIndexCountsAsEmptyIsEmptyWithoutFetching() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "eu", null)
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
        assertEquals(0, vm.items.value.size)
        assertEquals(0, repo.calls.size)
    }

    @Test
    fun aLayerMissingFromTheIndexIsEmptyWithoutFetching() {
        val repo = FakeRepository()
        val vm = LayerListViewModel(repo, "region", null)
        assertIs<LoadState.Loaded<Unit>>(vm.state.value)
        assertEquals(0, vm.items.value.size)
        assertEquals(0, repo.calls.size)
    }
}
