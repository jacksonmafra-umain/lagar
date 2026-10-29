package app.lagar.data

import app.lagar.domain.Scope
import app.lagar.domain.SearchMode
import app.lagar.domain.SearchQuery
import app.lagar.domain.SortOrder
import app.lagar.domain.StatusFilter
import kotlinx.coroutines.test.runTest
import kotlinx.datetime.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SearchServiceTest {
    /** Listings with entry-into-force dates, for the catalog path and the in-force filters. */
    private class Listings : LagarRepository {
        var listingCalls = 0
        val items = listOf(
            ListingItem("sfs-2010-800", "Skollag (2010:800)", "2010:800", "act", "2010-06-23", null, inForce = "2011-07-01"),
            ListingItem("sfs-1999-100", "Exempelförordning (1999:100)", "1999:100", "ordinance", "1999-03-25", "2005-01-01"),
            ListingItem("sfs-1974-152", "Regeringsformen", "1974:152", "fundamental_law", "1974-02-28", null, inForce = "2030-01-01"),
        )

        override suspend fun index() = ApiIndex(1, "t", listOf(ApiLayer("sfs", 3, listOf(ApiSeries("act", 2), ApiSeries("ordinance", 1)))))

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            listingCalls++
            return ListingPage(layer, type, 1, 1, items.size, if (layer == "sfs") items else emptyList())
        }

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    private val today = LocalDate(2026, 10, 29)

    private fun service(source: FakeSearchSource = FakeSearchSource(), listings: Listings = Listings()) =
        SearchService(FullTextIndex(source), Catalog(listings)) { today }

    private suspend fun SearchService.ids(q: SearchQuery, scope: Scope = Scope.Nationell) = search(q, scope).map { it.item.id }

    @Test
    fun fullTextFindsBodyMatchesAndRanksTitleMatchesFirst() = runTest {
        val s = service()
        assertEquals(emptyList(), s.ids(SearchQuery("utbildning")))
        assertEquals(listOf("sfs-2010-800"), s.ids(SearchQuery("utbildning", mode = SearchMode.FullText)))
        val hits = s.search(SearchQuery("forordning", mode = SearchMode.FullText), Scope.Nationell)
        assertTrue(hits.all { it.bodyOnly })
        assertEquals(listOf("sfs-2010-800", "sfs-1999-100"), hits.map { it.item.id })
    }

    @Test
    fun typeAheadMatchesTheWordBeingTyped() = runTest {
        assertEquals(listOf("sfs-2010-800"), service().ids(SearchQuery("skoll")))
        assertEquals(listOf("sfs-1974-152"), service().ids(SearchQuery("Regeringsf")))
    }

    @Test
    fun filtersApplyToDocRows() = runTest {
        val s = service()
        val q = SearchQuery("", status = StatusFilter.Repealed)
        assertEquals(listOf("sfs-1999-100"), s.ids(q))
        assertEquals(listOf("sfs-2010-800"), s.ids(SearchQuery("", types = setOf("act"))))
        assertEquals(listOf("sfs-2010-800", "sfs-1999-100"), s.ids(SearchQuery("", from = LocalDate(1999, 1, 1))))
    }

    @Test
    fun onlyTheScopesLayersAreSearched() = runTest {
        assertEquals(emptyList(), service().ids(SearchQuery("skollag"), Scope.Kommun))
    }

    @Test
    fun textOfOnlyDroppedWordsMatchesNothing() = runTest {
        assertEquals(emptyList(), service().ids(SearchQuery("och i ")))
    }

    @Test
    fun sortByNumber() = runTest {
        val ids = service().ids(SearchQuery("", status = StatusFilter.All, types = setOf("act", "ordinance", "fundamental_law"), sort = SortOrder.Number))
        assertEquals(listOf("sfs-1974-152", "sfs-1999-100", "sfs-2010-800"), ids)
    }

    @Test
    fun inForceFiltersReadTheDatesFromTheCatalogWhileDocsLackThem() = runTest {
        val listings = Listings()
        val s = service(listings = listings)
        assertEquals(listOf("sfs-1974-152"), s.ids(SearchQuery("", vacatioLegis = true)))
        assertEquals(listOf("sfs-2010-800"), s.ids(SearchQuery("", inForceTo = LocalDate(2020, 1, 1))))
        assertTrue(listings.listingCalls > 0)
    }

    @Test
    fun withoutInForceFiltersTheCatalogIsNotLoaded() = runTest {
        val listings = Listings()
        service(listings = listings).ids(SearchQuery("skollag"))
        assertEquals(0, listings.listingCalls)
    }

    @Test
    fun aMissingIndexFallsBackToTheCatalog() = runTest {
        val listings = Listings()
        val s = service(FakeSearchSource(missing = true), listings)
        assertEquals(listOf("sfs-2010-800"), s.ids(SearchQuery("skol")))
        assertTrue(listings.listingCalls > 0)
    }

    @Test
    fun withoutAnIndexTheCatalogIsUsed() = runTest {
        val s = SearchService(null, Catalog(Listings())) { today }
        assertEquals(listOf("sfs-1974-152"), s.ids(SearchQuery("regering")))
    }
}
