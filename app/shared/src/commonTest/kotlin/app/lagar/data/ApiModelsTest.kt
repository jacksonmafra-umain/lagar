package app.lagar.data

import app.lagar.domain.DisplayLayer
import app.lagar.domain.count
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
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
    fun decodesListingItemOptionalFields() {
        val sfs = json.decodeFromString<ListingPage>(ApiExamples.sfsListing)
        val skollag = sfs.items[0]
        assertEquals("2011-07-01", skollag.inForce)
        assertEquals("2026:1636", skollag.amendedThrough)
        assertEquals("Utbildningsdepartementet", skollag.ministry)
        val repealed = sfs.items[2]
        assertEquals("1999-07-01", repealed.inForce)
        assertNull(repealed.amendedThrough)
        assertNull(repealed.ministry)
    }

    @Test
    fun decodesLocalityIndexAndListings() {
        val index = json.decodeFromString<LocalityIndex>(ApiExamples.regionCodes)
        assertEquals("region_code", index.field)
        assertEquals(1, index.count("01"))
        assertEquals(0, index.count("12"))
        val region = json.decodeFromString<ListingPage>(ApiExamples.regionCodeListing).items.single()
        assertEquals("01", region.regionCode)
        assertNull(region.municipalityCode)
        val kommun = json.decodeFromString<ListingPage>(ApiExamples.municipalityCodeListing).items.single()
        assertEquals("01" to "0180", kommun.regionCode to kommun.municipalityCode)
        assertEquals(DisplayLayer.Municipality, DisplayLayer.forType(kommun.type))
        // Items of other layers carry the codes as null.
        assertNull(json.decodeFromString<ListingPage>(ApiExamples.sfsListing).items[0].regionCode)
    }

    @Test
    fun decodesLegacyListingWithoutOptionalFields() {
        val item = json.decodeFromString<ListingPage>(ApiExamples.legacyListing).items.single()
        assertEquals("sfs-2010-800", item.id)
        assertNull(item.inForce)
        assertNull(item.amendedThrough)
        assertNull(item.ministry)
        assertNull(item.regionCode)
        assertNull(item.municipalityCode)
        val strict = Json.decodeFromString<ListingPage>(ApiExamples.legacyListing).items.single()
        assertEquals(item, strict)
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
    fun legacyDocumentWithoutAmendmentsStillDecodes() {
        val legacy = Json.decodeFromString<DocumentResponse>(ApiExamples.legacyDocument)
        assertNull(legacy.meta.amendments)
        val current = json.decodeFromString<DocumentResponse>(ApiExamples.document)
        assertEquals(legacy, current)
    }

    @Test
    fun decodesTheAmendmentList() {
        val meta = json.decodeFromString<DocumentResponse>(ApiExamples.documentWithAmendments).meta
        assertEquals("1975-01-01", meta.inForce)
        assertEquals(listOf("2011:109"), meta.reprintedBy)
        val amendments = assertNotNull(meta.amendments)
        assertEquals(listOf("1976:871", "2022:1600"), amendments.map { it.number })
        assertEquals("Lag (1976:871) om ändring i regeringsformen", amendments[0].title)
        assertEquals("ändr. 1 kap 9 §", amendments[0].scope)
        assertEquals("Prop. 1975/76:209", amendments[0].preparatoryWorks)
        assertNull(amendments[0].inForce)
        assertEquals("2023-01-01", amendments[1].inForce)
        assertEquals("2023-01-01 överg.best.", amendments[1].inForceRaw)
        assertNull(amendments[1].title)
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
