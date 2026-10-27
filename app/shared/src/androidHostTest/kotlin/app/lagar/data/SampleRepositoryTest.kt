package app.lagar.data

import app.lagar.domain.DisplayLayer
import app.lagar.domain.count
import kotlinx.coroutines.test.runTest
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SampleRepositoryTest {
    // Compose resources are not available to JVM host tests, so read the bundled files from disk.
    private val repository = SampleRepository { path ->
        File("src/commonMain/composeResources/$path").readBytes()
    }

    @Test
    fun indexMatchesBundledSubset() = runTest {
        val index = repository.index()
        assertEquals(8, index.layers.size)
        assertEquals(6, index.count(DisplayLayer.SfsAct))
        assertEquals(4, index.count(DisplayLayer.SfsOrdinance))
        assertEquals(2, index.count(DisplayLayer.Fundamental))
        assertEquals(0, index.count(DisplayLayer.Eu))
    }

    @Test
    fun actsArePaginatedOverTwoPages() = runTest {
        val first = repository.listing("sfs", "act", 1)
        val second = repository.listing("sfs", "act", 2)
        assertEquals(2, first.pageCount)
        assertEquals(6, first.total)
        assertEquals(6, first.items.size + second.items.size)
        assertEquals(2, second.page)
    }

    @Test
    fun everyListedDocumentExists() = runTest {
        val listed = repository.listing("sfs", null, 1).items + repository.listing("fundamental", null, 1).items
        assertEquals(12, listed.size)
        listed.forEach { assertEquals(it.id, repository.document(it.id).meta.id) }
    }

    @Test
    fun regeringsformenHasLongBodyAndNSeriesNumbersDecode() = runTest {
        assertTrue(repository.document("sfs-1974-152").body.length > 50_000)
        val n = repository.document("sfs-n2026-1")
        assertEquals("N2026:1", n.meta.number)
    }

    @Test
    fun emptyLayerListingIsEmptyPage() = runTest {
        val page = repository.listing("eu", null, 1)
        assertEquals(0, page.total)
        assertEquals(1, page.pageCount)
        assertTrue(page.items.isEmpty())
    }
}
