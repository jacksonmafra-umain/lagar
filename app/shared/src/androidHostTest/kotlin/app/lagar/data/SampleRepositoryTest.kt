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

    @Test
    fun everyBundledMinistryListingMatchesItsIndex() = runTest {
        for (type in listOf("act", "ordinance")) {
            val index = repository.ministries("sfs", type)
            assertEquals(repository.listing("sfs", type, 1).total, index.total)
            assertEquals(index.total, index.ministries.sumOf { it.count } + index.unassigned)
            index.ministries.forEach { ministry ->
                val page = repository.ministryListing("sfs", type, ministry.id, 1)
                assertEquals(ministry.count, page.total, ministry.id)
                assertTrue(page.items.all { it.ministry?.startsWith(ministry.name) == true }, ministry.id)
            }
        }
    }

    @Test
    fun bundledLocalityListingsMatchTheirIndexes() = runTest {
        for ((layer, field) in listOf("region" to "region_code", "municipality" to "municipality_code")) {
            val index = repository.localities(layer)
            assertEquals(field, index.field)
            assertEquals(repository.listing(layer, null, 1).total, index.total)
            assertTrue(index.codes.isNotEmpty(), layer)
            index.codes.forEach { entry ->
                val page = repository.localityListing(layer, entry.code, 1)
                assertEquals(entry.count, page.total, entry.code)
                val codes = page.items.map { if (layer == "region") it.regionCode else it.municipalityCode }
                assertTrue(codes.all { it == entry.code }, entry.code)
                page.items.forEach { assertEquals(it.id, repository.document(it.id).meta.id) }
            }
        }
        assertEquals(2, repository.localities("region").count("01"))
        assertEquals(2, repository.localities("municipality").count("0180"))
    }
}
