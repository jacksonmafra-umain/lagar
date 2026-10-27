package app.lagar.ui.list

import app.lagar.data.DocumentResponse
import app.lagar.data.ApiIndex
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.data.ListingPage
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

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            calls += page
            gates[page]?.await()
            if (page in failing) throw IllegalStateException("boom")
            return ListingPage(
                layer, type, page, pageCount, total = pageCount * 2,
                items = listOf(
                    ListingItem("id-$page-a", "A$page", "$page:1", "act", null, null),
                    ListingItem("id-$page-b", "B$page", "$page:2", "act", null, null),
                ),
            )
        }

        override suspend fun index(): ApiIndex = error("unused")
        override suspend fun document(id: String): DocumentResponse = error("unused")
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
}
