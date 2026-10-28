package app.lagar.ui.search

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.Catalog
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.data.ListingPage
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import app.lagar.domain.SearchMode
import app.lagar.domain.SearchQuery
import app.lagar.domain.StatusFilter
import app.lagar.settings.UserPreferences
import app.lagar.ui.navigation.Search
import com.russhwolf.settings.MapSettings
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.datetime.LocalDate
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

@OptIn(ExperimentalCoroutinesApi::class)
class SearchViewModelTest {
    @BeforeTest
    fun setUp() = Dispatchers.setMain(StandardTestDispatcher())

    @AfterTest
    fun tearDown() = Dispatchers.resetMain()

    /** A catalog over a fake repository that counts how often the index is read. */
    private class FakeRepository : LagarRepository {
        var indexCalls = 0
        var listingCalls = 0
        var gate: CompletableDeferred<Unit>? = null
        val items = listOf(
            ListingItem("1", "Regeringsformen", "1974:152", "fundamental_law", "1974-02-28", null),
            ListingItem("2", "Skollag", "2010:800", "act", "2010-06-23", null),
        )

        override suspend fun index(): ApiIndex {
            indexCalls++
            return ApiIndex(1, "t", listOf(ApiLayer("fundamental", 2, emptyList())))
        }

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            listingCalls++
            gate?.await()
            return ListingPage(layer, type, page, 1, items.size, items)
        }

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    private fun viewModel(repo: FakeRepository, scope: Scope = Scope.Nationell, initial: SearchQuery = SearchQuery("")): SearchViewModel {
        val prefs = UserPreferences(MapSettings())
        prefs.setScope(scope)
        return SearchViewModel(Catalog(repo), prefs, initial)
    }

    private fun SearchViewModel.ids() = assertIs<LoadState.Loaded<List<ListingItem>>>(results.value).value.map { it.id }

    @Test
    fun blankQueryResolvesToTheHintWithoutLoadingTheCatalog() = runTest {
        val repo = FakeRepository()
        val vm = viewModel(repo)
        runCurrent()
        assertEquals(emptyList(), vm.ids())
        assertEquals(0, repo.indexCalls)
    }

    @Test
    fun whitespaceOnlyQueryResolvesToNothingWithoutLoadingTheCatalog() = runTest {
        val repo = FakeRepository()
        val vm = viewModel(repo)
        runCurrent()
        vm.update(SearchQuery("   "))
        advanceTimeBy(300)
        runCurrent()
        assertEquals(emptyList(), vm.ids())
        assertEquals(0, repo.indexCalls)
    }

    @Test
    fun aQueryWithNoMatchResolvesToAnEmptyList() = runTest {
        val vm = viewModel(FakeRepository(), initial = SearchQuery("zzz"))
        runCurrent()
        assertEquals(emptyList(), vm.ids())
    }

    @Test
    fun changingTheScopeRerunsTheSearch() = runTest {
        val prefs = UserPreferences(MapSettings())
        val vm = SearchViewModel(Catalog(FakeRepository()), prefs, SearchQuery("skol"))
        runCurrent()
        assertEquals(listOf("2"), vm.ids())
        prefs.setScope(Scope.Kommun)
        runCurrent()
        assertEquals(emptyList(), vm.ids())
        prefs.setScope(Scope.Nationell)
        runCurrent()
        assertEquals(listOf("2"), vm.ids())
    }

    @Test
    fun typingSearchesOnlyAfterTheDebounce() = runTest {
        val repo = FakeRepository()
        val vm = viewModel(repo)
        runCurrent()
        vm.update(SearchQuery("regering"))
        advanceTimeBy(200)
        runCurrent()
        assertEquals(0, repo.indexCalls)
        advanceTimeBy(60)
        runCurrent()
        assertEquals(listOf("1"), vm.ids())
    }

    @Test
    fun theFirstQueryShowsProgressWhileTheCatalogLoadsAndLaterOnesReuseIt() = runTest {
        val repo = FakeRepository()
        val vm = viewModel(repo)
        runCurrent()
        assertEquals(emptyList(), vm.ids())
        val gate = CompletableDeferred<Unit>()
        repo.gate = gate
        vm.update(SearchQuery("skol"))
        advanceTimeBy(300)
        runCurrent()
        assertIs<LoadState.Loading>(vm.results.value)
        gate.complete(Unit)
        runCurrent()
        assertEquals(listOf("2"), vm.ids())
        assertEquals(1, repo.listingCalls)
        repo.gate = CompletableDeferred()
        vm.update(SearchQuery("regering"))
        advanceTimeBy(300)
        runCurrent()
        assertEquals(listOf("1"), vm.ids())
        assertEquals(1, repo.listingCalls)
    }

    @Test
    fun theRouteQueryRunsAtOnce() = runTest {
        val vm = viewModel(FakeRepository(), initial = SearchQuery("2010:800", mode = SearchMode.Number))
        runCurrent()
        assertEquals(listOf("2"), vm.ids())
    }

    @Test
    fun kommunScopeNeverTouchesTheCatalog() = runTest {
        val repo = FakeRepository()
        val vm = viewModel(repo, Scope.Kommun, SearchQuery("skol"))
        runCurrent()
        assertEquals(emptyList(), vm.ids())
        assertEquals(0, repo.indexCalls)
    }

    @Test
    fun routeArgumentsRoundTripTheQuery() {
        val query = SearchQuery(
            text = "skol",
            types = setOf("act", "ordinance"),
            from = LocalDate(2026, 6, 1),
            to = LocalDate(2026, 6, 30),
            mode = SearchMode.Title,
            status = StatusFilter.InForce,
        )
        assertEquals(query, query.toRoute().toQuery())
        assertEquals(Search(text = "x"), SearchQuery("x").toRoute())
    }

    @Test
    fun staleRouteValuesFallBackToDefaults() {
        val query = Search(text = "x", from = "nope", mode = "Gone", status = "Gone").toQuery()
        assertEquals(SearchQuery("x"), query)
    }

    @Test
    fun parseDateAcceptsOnlyRealIsoDates() {
        assertEquals(LocalDate(2026, 6, 1), parseDate(" 2026-06-01 "))
        assertEquals(null, parseDate("2026-02-30"))
        assertEquals(null, parseDate("01/06/2026"))
    }
}
