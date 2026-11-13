package app.lagar.data

import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ServiceModelsTest {
    private val json = Json { ignoreUnknownKeys = true }

    private val catalog get() = json.decodeFromString<ServiceCatalog>(ApiExamples.serviceCatalog)

    @Test
    fun decodesTheExampleCatalogue() {
        val catalog = catalog
        assertEquals(3, catalog.total)
        assertEquals(
            listOf("service-adoptionsbidrag", "service-forskola", "service-registerutdrag-skola-forskola"),
            catalog.services.map { it.id },
        )
        val forskola = catalog.services[1]
        assertEquals("Förskola", forskola.title)
        assertEquals("Kommunen", forskola.issuer)
        assertEquals(listOf("private"), forskola.audience)
        assertEquals(listOf("family", "education"), forskola.topics)
        assertEquals(listOf("online"), forskola.channels)
        assertEquals("municipality", forskola.scope)
        assertEquals(true, forskola.template)
        assertNull(forskola.regionCode)
        assertNull(forskola.municipalityCode)
        assertEquals("https://www.skolverket.se/for-dig-som-ar/elev-eller-foralder/forskola", forskola.source)
        assertNull(forskola.serviceUrl)
        assertEquals(listOf(ServiceNormRef("sfs-2010-800", "Skollag (2010:800)", "act", "sfs")), forskola.basedOn)
    }

    @Test
    fun decodesServiceUrlEmptyChannelsAndEveryBasedOnReference() {
        val registerutdrag = catalog.services[2]
        assertEquals(
            "https://polisen.se/tjanster-tillstand/belastningsregistret/skola-eller-forskola/e-tjanst/",
            registerutdrag.serviceUrl,
        )
        assertEquals(listOf("sfs-1998-620", "sfs-2010-800"), registerutdrag.basedOn.map { it.id })
        assertEquals(emptyList(), catalog.services[0].channels)
    }

    @Test
    fun decodesTheExampleByNormIndex() {
        val index = json.decodeFromString<ServiceNormIndex>(ApiExamples.serviceByNorm)
        assertEquals(setOf("sfs-1998-620", "sfs-2010-110", "sfs-2010-800"), index.norms.keys)
        assertEquals(
            listOf("service-forskola", "service-registerutdrag-skola-forskola"),
            index.serviceIds("sfs-2010-800"),
        )
        assertEquals(emptyList(), index.serviceIds("sfs-1999-175"))
    }

    @Test
    fun emptyServiceLayerDecodes() {
        val catalog = json.decodeFromString<ServiceCatalog>("""{"total": 0, "services": []}""")
        assertEquals(ServiceCatalog(0, emptyList()), catalog)
        assertEquals(ServiceNormIndex(emptyMap()), json.decodeFromString<ServiceNormIndex>("""{"norms": {}}"""))
    }

    @Test
    fun decodesTheServiceFieldsOfAPublicServiceDocument() {
        val meta = json.decodeFromString<DocumentResponse>(ApiExamples.serviceDocument).meta
        assertEquals("public_service", meta.type)
        assertEquals("service", meta.layer)
        assertNull(meta.issued)
        assertEquals(listOf("sfs-1998-620", "sfs-2010-800"), meta.basedOn)
        assertEquals(listOf("private"), meta.audience)
        assertEquals(listOf("legal", "education", "work"), meta.topics)
        assertEquals(listOf("online", "form"), meta.channels)
        assertEquals(
            "https://polisen.se/tjanster-tillstand/belastningsregistret/skola-eller-forskola/e-tjanst/",
            meta.serviceUrl,
        )
        assertEquals("202100-0076", meta.issuerOrgNumber)
        assertEquals("national", meta.scope)
        assertEquals(false, meta.template)
    }

    @Test
    fun otherDocumentsServeTheServiceFieldsAsNull() {
        val current = json.decodeFromString<DocumentResponse>(ApiExamples.document).meta
        val legacy = Json.decodeFromString<DocumentResponse>(ApiExamples.legacyDocument).meta
        for (meta in listOf(current, legacy)) {
            assertNull(meta.basedOn)
            assertNull(meta.audience)
            assertNull(meta.topics)
            assertNull(meta.channels)
            assertNull(meta.serviceUrl)
            assertNull(meta.issuerOrgNumber)
            assertNull(meta.scope)
            assertNull(meta.template)
        }
    }
}
