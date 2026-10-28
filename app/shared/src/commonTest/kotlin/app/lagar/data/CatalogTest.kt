package app.lagar.data

import app.lagar.domain.Scope
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals

class CatalogTest {
    private class FakeRepository(
        val index: ApiIndex,
        val pages: Map<Triple<String, String?, Int>, ListingPage>,
    ) : LagarRepository {
        val requests = mutableListOf<Triple<String, String?, Int>>()

        override suspend fun index() = index

        override suspend fun listing(layer: String, type: String?, page: Int): ListingPage {
            val key = Triple(layer, type, page)
            requests += key
            return pages.getValue(key)
        }

        override suspend fun document(id: String): DocumentResponse = error("unused")
    }

    private fun item(id: String, issued: String?) = ListingItem(id, id, id, "act", issued, null)

    private fun page(layer: String, type: String?, page: Int, count: Int, vararg items: ListingItem) =
        ListingPage(layer, type, page, count, items.size, items.toList())

    private fun repo(index: ApiIndex, vararg pages: ListingPage) =
        FakeRepository(index, pages.associateBy { Triple(it.layer, it.type, it.page) })

    @Test
    fun loadsAllPagesOnce() = runTest {
        val index = ApiIndex(1, "t", listOf(ApiLayer("sfs", 3, listOf(ApiSeries("act", 3)))))
        val fake = repo(
            index,
            page("sfs", "act", 1, 2, item("a", "2020-01-01"), item("b", "2021-01-01")),
            page("sfs", "act", 2, 2, item("c", "2019-01-01")),
        )
        val catalog = Catalog(fake)
        assertEquals(3, catalog.items(Scope.Nationell).size)
        assertEquals(3, catalog.items(Scope.Nationell).size)
        assertEquals(listOf<Triple<String, String?, Int>>(Triple("sfs", "act", 1), Triple("sfs", "act", 2)), fake.requests)
    }

    @Test
    fun keepsPageOrderAcrossManyPages() = runTest {
        val index = ApiIndex(1, "t", listOf(ApiLayer("sfs", 9, listOf(ApiSeries("act", 9)))))
        val pages = (1..9).map { page("sfs", "act", it, 9, item("p$it", "2020-01-01")) }
        val fake = repo(index, *pages.toTypedArray())
        assertEquals((1..9).map { "p$it" }, Catalog(fake).items(Scope.Nationell).map { it.id })
        assertEquals(9, fake.requests.size)
    }

    @Test
    fun skipsEmptyLayers() = runTest {
        val index = ApiIndex(
            1,
            "t",
            listOf(ApiLayer("sfs", 1, listOf(ApiSeries("act", 1), ApiSeries("ordinance", 0))), ApiLayer("eu", 0, emptyList())),
        )
        val fake = repo(index, page("sfs", "act", 1, 1, item("a", "2020-01-01")))
        assertEquals(listOf("a"), Catalog(fake).items(Scope.Nationell).map { it.id })
        assertEquals(listOf<Triple<String, String?, Int>>(Triple("sfs", "act", 1)), fake.requests)
        assertEquals(emptyList<ListingItem>(), Catalog(fake).items(Scope.Kommun))
        assertEquals(1, fake.requests.size)
    }

    @Test
    fun sortedIssuedDescNullsLast() = runTest {
        val index = ApiIndex(
            1,
            "t",
            listOf(ApiLayer("sfs", 2, listOf(ApiSeries("act", 2))), ApiLayer("eu", 2, emptyList())),
        )
        val fake = repo(
            index,
            page("sfs", "act", 1, 1, item("old", "2010-01-01"), item("none", null)),
            page("eu", null, 1, 1, item("new", "2024-05-01"), item("mid", "2015-02-02")),
        )
        assertEquals(listOf("new", "mid", "old", "none"), Catalog(fake).items(Scope.Nationell).map { it.id })
    }
}
