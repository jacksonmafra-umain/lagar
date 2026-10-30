package app.lagar.ui.home

import app.lagar.data.ApiException
import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.data.Catalog
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.data.ListingPage
import app.lagar.domain.DisplayLayer
import app.lagar.domain.Scope
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class HomeFeedTest {
    /** Serves each listing in pages of [pageSize], newest first, and records every page request. */
    private class FakeRepository(
        private val listings: Map<Pair<String, String?>, List<ListingItem>>,
        private val pageSize: Int,
    ) : LagarRepository {
        val requests = mutableListOf<Triple<String, String?, Int>>()

        override suspend fun index(): ApiIndex {
            val layers = listings.keys.map { it.first }.distinct().map { layer ->
                val series = listings.filterKeys { it.first == layer && it.second != null }.map { (k, v) -> ApiSeries(k.second!!, v.size) }
                ApiLayer(layer, listings[layer to null]?.size ?: series.sumOf { it.count }, series)
            }
            return ApiIndex(1, "t", layers)
        }

        /** Listings whose requests fail, as during a deploy that has not reached the API yet. */
        val failing = mutableSetOf<Pair<String, String?>>()

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            requests += Triple(layer, type, page)
            if ((layer to type) in failing) throw ApiException("unavailable", 404)
            val all = listings.getValue(layer to type)
            val pageCount = maxOf(1, (all.size + pageSize - 1) / pageSize)
            return ListingPage(layer, type, page, pageCount, all.size, all.drop((page - 1) * pageSize).take(pageSize))
        }

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    /** [count] items of [type], one a day going back from [start] in steps of [step] days. */
    private fun items(prefix: String, type: String, count: Int, start: Int, step: Int) = List(count) { i ->
        val day = start - i * step
        val issued = "20${(day / 365).toString().padStart(2, '0')}-${(day % 365 / 31 + 1).toString().padStart(2, '0')}-${(day % 31 + 1).toString().padStart(2, '0')}"
        ListingItem("$prefix-$i", "$prefix $i", "$i", type, issued, null)
    }.sortedWith(compareByDescending { it.issued })

    private fun corpus(acts: Int, ordinances: Int) = mapOf(
        ("fundamental" to null) to items("rf", "fundamental_law", 4, 2000, 300),
        ("sfs" to "act") to items("act", "act", acts, 9000, 3),
        ("sfs" to "ordinance") to items("ord", "ordinance", ordinances, 8999, 2),
    )

    private suspend fun feed(repo: LagarRepository) = loadHomeFeed(repo, repo.index(), Scope.Nationell, importantLimit = 5, recentLimit = 20)

    private suspend fun expected(repo: LagarRepository): HomeFeed {
        val items = Catalog(repo).items(Scope.Nationell)
        return HomeFeed(
            fundamental = items.filter { it.type == "fundamental_law" },
            acts = items.filter { it.type == "act" }.take(5),
            ordinances = items.filter { it.type == "ordinance" }.take(5),
            recent = items.take(20),
            hasMoreRecent = items.size > 20,
        )
    }

    @Test
    fun aLargeCatalogLoadsOnlyTheFirstPageOfEachLevel() = runTest {
        val repo = FakeRepository(corpus(acts = 500, ordinances = 400), pageSize = 50)
        val feed = feed(repo)
        assertEquals(
            setOf<Triple<String, String?, Int>>(Triple("fundamental", null, 1), Triple("sfs", "act", 1), Triple("sfs", "ordinance", 1)),
            repo.requests.toSet(),
        )
        assertEquals(3, repo.requests.size)
        assertTrue(feed.hasMoreRecent)
        assertEquals(expected(FakeRepository(corpus(500, 400), 50)), feed)
    }

    @Test
    fun smallPagesLoadFurtherPagesOnlyUntilTheListsAreComplete() = runTest {
        val repo = FakeRepository(corpus(acts = 30, ordinances = 30), pageSize = 3)
        val feed = feed(repo)
        assertEquals(expected(FakeRepository(corpus(30, 30), 3)), feed)
        // 20 recent items out of two interleaved series need about 10 of each, so 4 pages of 3, not all 10.
        assertTrue(repo.requests.count { it.second == "act" } < 10)
        assertTrue(repo.requests.count { it.second == "ordinance" } < 10)
    }

    @Test
    fun aSmallCatalogMatchesTheFullCatalog() = runTest {
        val repo = FakeRepository(corpus(acts = 6, ordinances = 4), pageSize = 3)
        val feed = feed(repo)
        assertEquals(expected(FakeRepository(corpus(6, 4), 3)), feed)
        assertFalse(feed.hasMoreRecent)
    }

    @Test
    fun emptyLevelsAreNotRequested() = runTest {
        val repo = FakeRepository(corpus(acts = 6, ordinances = 0) + (("eu" to null) to emptyList()), pageSize = 50)
        feed(repo)
        assertEquals(setOf("fundamental", "act"), repo.requests.map { it.second ?: it.first }.toSet())
    }

    @Test
    fun aFailingLevelIsLeftOutAndReported() = runTest {
        val repo = FakeRepository(corpus(acts = 6, ordinances = 4), pageSize = 3).apply { failing += "sfs" to "ordinance" }
        val feed = feed(repo)
        assertEquals(listOf(DisplayLayer.SfsOrdinance), feed.unavailable)
        assertEquals(emptyList(), feed.ordinances)
        assertEquals(5, feed.acts.size)
        assertEquals(4, feed.fundamental.size)
        assertTrue(feed.recent.none { it.type == "ordinance" })
    }

    @Test
    fun everyLevelFailingFailsTheFeed() = runTest {
        val repo = FakeRepository(corpus(acts = 6, ordinances = 4), pageSize = 3).apply {
            failing += listOf("fundamental" to null, "sfs" to "act", "sfs" to "ordinance")
        }
        assertFailsWith<ApiException> { feed(repo) }
    }
}
