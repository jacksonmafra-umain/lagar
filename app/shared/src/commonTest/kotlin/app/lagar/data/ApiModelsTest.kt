package app.lagar.data

import app.lagar.domain.DisplayLayer
import app.lagar.domain.count
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ApiModelsTest {
    private val json = Json { ignoreUnknownKeys = true }

    private fun layer(id: String, count: Int, vararg series: Pair<String, Int>) =
        ApiLayer(id, count, series.map { ApiSeries(it.first, it.second) })

    @Test
    fun decodesExampleIndex() {
        val index = json.decodeFromString<ApiIndex>(ApiExamples.index)
        assertEquals(1, index.apiVersion)
        assertEquals("2026-10-27T10:30:00Z", index.builtAt)
        assertEquals(8, index.layers.size)
        assertEquals(listOf("act", "ordinance"), index.layers[1].series.map { it.id })
    }

    @Test
    fun decodesExampleListings() {
        val sfs = json.decodeFromString<ListingPage>(ApiExamples.sfsListing)
        assertNull(sfs.type)
        assertEquals(3, sfs.total)
        assertEquals("2005-01-01", sfs.items[2].repealed)
        val acts = json.decodeFromString<ListingPage>(ApiExamples.actListing)
        assertEquals("act", acts.type)
        assertEquals(1, acts.pageCount)
        assertEquals("2010:800", acts.items.single().number)
    }

    @Test
    fun decodesExampleDocumentWithAmendedThrough() {
        val doc = json.decodeFromString<DocumentResponse>(ApiExamples.document)
        assertEquals("sfs-1999-175", doc.meta.id)
        assertEquals("2026:851", doc.meta.amendedThrough)
        assertNull(doc.meta.inForce)
        assertNull(doc.meta.eli)
        assertEquals(emptyList(), doc.meta.amendedBy)
        assertEquals("Justitiedepartementet KRIM", doc.meta.ministry)
        assertEquals(false, doc.meta.authoritative)
        assertEquals("sv", doc.meta.language)
    }

    @Test
    fun countsSfsDisplayLevelsFromSeries() {
        val index = json.decodeFromString<ApiIndex>(ApiExamples.index)
        assertEquals(1, index.count(DisplayLayer.SfsAct))
        assertEquals(2, index.count(DisplayLayer.SfsOrdinance))
        assertEquals(0, index.count(DisplayLayer.Fundamental))
    }

    @Test
    fun missingSeriesCountsAsZero() {
        val index = ApiIndex(1, "t", listOf(layer("sfs", 3, "ordinance" to 3)))
        assertEquals(0, index.count(DisplayLayer.SfsAct))
        assertEquals(3, index.count(DisplayLayer.SfsOrdinance))
    }

    @Test
    fun emptyOrMissingLayerCountsAsZero() {
        val index = ApiIndex(1, "t", listOf(layer("sfs", 0)))
        assertEquals(0, index.count(DisplayLayer.SfsAct))
        assertEquals(0, index.count(DisplayLayer.Eu))
    }

    @Test
    fun fundamentalUsesLayerCount() {
        val index = ApiIndex(1, "t", listOf(layer("fundamental", 2, "fundamental_law" to 2)))
        assertEquals(2, index.count(DisplayLayer.Fundamental))
    }

    @Test
    fun displayLayersAreOrderedAndMapped() {
        assertEquals(
            listOf("fundamental", "sfs", "sfs", "agency", "case_law", "eu", "region", "municipality", "service"),
            DisplayLayer.entries.map { it.apiLayer },
        )
        assertEquals(listOf(null, "act", "ordinance"), DisplayLayer.entries.take(3).map { it.apiType })
    }
}
