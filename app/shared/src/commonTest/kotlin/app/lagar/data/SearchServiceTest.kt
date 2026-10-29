package app.lagar.data

import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.SearchMode
import app.lagar.domain.SearchQuery
import app.lagar.domain.SortOrder
import app.lagar.domain.StatusFilter
import kotlinx.coroutines.test.runTest
import kotlinx.datetime.LocalDate
import kotlinx.serialization.json.JsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
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
        val source = FakeSearchSource()
        assertEquals(emptyList(), service(source).ids(SearchQuery("skollag"), Scope.Kommun))
        // The index has no municipal group, so nothing beyond the manifest is read.
        assertEquals(emptyList(), source.docsRequests)
        assertEquals(emptyList(), source.shardRequests)
        val v1 = FakeSearchSource(version = 1)
        assertEquals(emptyList(), service(v1).ids(SearchQuery("skollag"), Scope.Kommun))
    }

    @Test
    fun hitsFromSeveralGroupsAreMerged() = runTest {
        val source = FakeSearchSource()
        // `fo` is a prefix of `foreskrift` (fundamental) and `forordning` (sfs).
        val ids = service(source).ids(SearchQuery("fo", mode = SearchMode.FullText))
        assertEquals(setOf("sfs-1974-152", "sfs-1999-100", "sfs-2010-800"), ids.toSet())
        assertEquals(3, ids.size)
        assertEquals(setOf("fundamental/fo", "sfs/fo"), source.shardRequests.toSet())
        assertEquals(setOf<String?>("fundamental", "sfs"), source.docsRequests.toSet())
    }

    @Test
    fun bothIndexVersionsGiveTheSameResults() = runTest {
        val queries = listOf(
            SearchQuery("utbildning", mode = SearchMode.FullText),
            SearchQuery("forordning", mode = SearchMode.FullText),
            SearchQuery("skoll"),
            SearchQuery("Regeringsf"),
            SearchQuery("1999:100", mode = SearchMode.Number),
            SearchQuery("fo", mode = SearchMode.FullText),
            SearchQuery("19", sort = SortOrder.Newest),
            SearchQuery("", status = StatusFilter.Repealed),
            SearchQuery("", from = LocalDate(1999, 1, 1)),
        )
        for (q in queries) {
            assertEquals(service(FakeSearchSource(version = 1)).ids(q), service(FakeSearchSource(version = 2)).ids(q), q.toString())
        }
    }

    @Test
    fun warmOnceTheScopesDocumentTablesAreLoaded() = runTest {
        val s = service()
        assertFalse(s.isWarm(Scope.Nationell))
        s.ids(SearchQuery("skollag"))
        assertTrue(s.isWarm(Scope.Nationell))
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

    /** Two län and two kommuner: county regulations of Stockholm (01) and Skåne (12), municipal ones of 0180 and 1280. */
    private class LocalListings : LagarRepository {
        val region = listOf(
            ListingItem("01fs-2026-3", "Naturreservatet Vindsjöbergen", "01FS 2026:3", "county_regulation", "2026-01-27", null, regionCode = "01"),
            ListingItem("12fs-2026-1", "Naturreservatet Exempel", "12FS 2026:1", "county_regulation", "2026-01-02", null, regionCode = "12"),
        )
        val municipality = listOf(
            ListingItem("0180-kfs-2013-19", "Lokala hälsoföreskrifter", "KFS 2013:19", "municipal_regulation", null, null, regionCode = "01", municipalityCode = "0180"),
            ListingItem("1280-1", "Lokala hälsoföreskrifter", "MFS 1", "municipal_regulation", null, null, regionCode = "12", municipalityCode = "1280"),
        )

        override suspend fun index() = ApiIndex(
            1,
            "t",
            listOf(ApiLayer("region", 2, listOf(ApiSeries("county_regulation", 2))), ApiLayer("municipality", 2, listOf(ApiSeries("municipal_regulation", 2)))),
        )

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            val items = if (layer == "region") region else if (layer == "municipality") municipality else emptyList()
            return ListingPage(layer, type, 1, 1, items.size, items)
        }

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    /** A search index without shards whose document table holds [LocalListings] with their locality codes. */
    private class LocalIndex(private val rows: List<ListingItem>) : SearchIndexSource {
        override suspend fun searchManifest() = SearchManifest(1, "t", rows.size, listOf("title", "number"), mapOf("title" to 1, "number" to 2), 2, emptyList())

        override suspend fun searchGroupManifest(group: String): SearchGroupManifest = error("version 1")

        override suspend fun searchDocs(group: String?) = SearchDocsTable(
            listOf("id", "title", "number", "type", "issued", "repealed", "region_code", "municipality_code"),
            rows.map { r ->
                listOf(r.id, r.title, r.number, r.type, r.issued, r.repealed, r.regionCode, r.municipalityCode).map { JsonPrimitive(it) }
            },
        )

        override suspend fun searchShard(group: String?, key: String): SearchShard = error("no shards")
    }

    @Test
    fun regionAndKommunSearchOnlyTheChosenLocality() = runTest {
        val listings = LocalListings()
        val catalog = SearchService(null, Catalog(listings)) { today }
        val indexed = SearchService(FullTextIndex(LocalIndex(listings.region + listings.municipality)), Catalog(listings)) { today }
        val stockholm = Locality("01", "0180")
        // The index has no shards, so the text query runs on the catalog and the filter-only ones on both.
        assertEquals(listOf("01fs-2026-3"), catalog.search(SearchQuery("naturreservatet"), Scope.Region, stockholm).map { it.item.id })
        assertEquals(emptyList(), catalog.search(SearchQuery("halsoforeskrifter"), Scope.Kommun, Locality(null, null)))
        for (s in listOf(catalog, indexed)) {
            val county = SearchQuery("", types = setOf("county_regulation"))
            assertEquals(listOf("01fs-2026-3"), s.search(county, Scope.Region, stockholm).map { it.item.id })
            assertEquals(listOf("12fs-2026-1"), s.search(county, Scope.Region, Locality("12", null)).map { it.item.id })
            val municipal = SearchQuery("", types = setOf("municipal_regulation"))
            assertEquals(listOf("0180-kfs-2013-19"), s.search(municipal, Scope.Kommun, stockholm).map { it.item.id })
            assertEquals(emptyList(), s.search(municipal, Scope.Kommun, Locality(null, null)))
            // National search leaves out the regional and municipal layers.
            assertEquals(emptyList(), s.search(county, Scope.Nationell, stockholm))
        }
    }

    @Test
    fun docsTableReadsTheLocalityColumns() {
        val table = SearchDocsTable(
            listOf("id", "title", "number", "type", "issued", "repealed", "region_code", "municipality_code"),
            listOf(listOf("0180-x", "T", "KFS 1", "municipal_regulation", null, null, "01", "0180").map { JsonPrimitive(it) }),
        )
        assertEquals("01" to "0180", table.items().single().let { it.regionCode to it.municipalityCode })
        val legacy = SearchDocsTable(listOf("id", "title"), listOf(listOf(JsonPrimitive("a"), JsonPrimitive("A"))))
        assertEquals(null, legacy.items().single().regionCode)
    }
}
