package app.lagar.ui.home

import app.lagar.data.ApiException
import app.lagar.data.ListingItem
import app.lagar.data.ListingPage
import app.lagar.data.LocalityCount
import app.lagar.data.LocalityIndex
import app.lagar.data.LocalityRepository
import app.lagar.domain.DisplayLayer
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class LocalityFeedTest {
    /** Serves per-code listings in pages of [pageSize] and records the requests; [missing] answers 404 for the index. */
    private class FakeLocalities(
        private val byCode: Map<String, List<ListingItem>>,
        private val pageSize: Int = 50,
        private val missing: Boolean = false,
    ) : LocalityRepository {
        val requests = mutableListOf<String>()

        override suspend fun localities(layer: String): LocalityIndex {
            requests += "$layer/index"
            if (missing) throw ApiException("missing", 404)
            return LocalityIndex(layer, "region_code", byCode.values.sumOf { it.size }, byCode.map { (c, v) -> LocalityCount(c, v.size) })
        }

        override suspend fun localityListing(layer: String, code: String, page: Int): ListingPage {
            requests += "$layer/$code/$page"
            val all = byCode.getValue(code)
            val pageCount = maxOf(1, (all.size + pageSize - 1) / pageSize)
            return ListingPage(layer, null, page, pageCount, all.size, all.drop((page - 1) * pageSize).take(pageSize))
        }
    }

    private fun regs(count: Int, repealedFirst: Int = 0) = List(count) { i ->
        ListingItem("01fs-$i", "Föreskrift $i", "01FS 2026:${count - i}", "county_regulation", "2026-01-01", if (i < repealedFirst) "2026-06-01" else null, regionCode = "01")
    }

    @Test
    fun loadsOnlyTheChosenCodesFirstPage() = runTest {
        val source = FakeLocalities(mapOf("01" to regs(30), "12" to regs(3)))
        val feed = loadLocalityFeed(source, DisplayLayer.Region, "01", keyLimit = 5, recentLimit = 20)
        assertEquals(listOf("region/index", "region/01/1"), source.requests)
        assertEquals(30, feed.total)
        assertEquals(regs(30).take(5), feed.key)
        assertEquals(regs(30).take(20), feed.recent)
        assertTrue(feed.hasMoreRecent)
    }

    @Test
    fun keyRulesSkipRepealedDocumentsAndReadOnUntilFiveAreInForce() = runTest {
        val source = FakeLocalities(mapOf("01" to regs(12, repealedFirst = 8)), pageSize = 5)
        val feed = loadLocalityFeed(source, DisplayLayer.Region, "01", keyLimit = 5, recentLimit = 20)
        assertEquals(listOf("region/index", "region/01/1", "region/01/2", "region/01/3"), source.requests)
        assertEquals((8 until 12).map { "01fs-$it" }, feed.key.map { it.id })
        assertTrue(feed.key.all { it.repealed == null })
        assertFalse(feed.hasMoreRecent)
    }

    @Test
    fun anUnlistedCodeOrMissingIndexIsEmptyWithoutListingRequests() = runTest {
        val source = FakeLocalities(mapOf("01" to regs(2)))
        assertEquals(LocalityFeed.Empty, loadLocalityFeed(source, DisplayLayer.Region, "12", 5, 20))
        assertEquals(listOf("region/index"), source.requests)
        val old = FakeLocalities(mapOf("01" to regs(2)), missing = true)
        assertEquals(LocalityFeed.Empty, loadLocalityFeed(old, DisplayLayer.Region, "01", 5, 20))
        assertEquals(listOf("region/index"), old.requests)
    }
}
