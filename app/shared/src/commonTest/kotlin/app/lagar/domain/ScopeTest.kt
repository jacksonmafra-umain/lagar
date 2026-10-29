package app.lagar.domain

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.data.ListingItem
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ScopeTest {
    private val index = ApiIndex(
        apiVersion = 1,
        builtAt = "2026-10-27T00:00:00Z",
        layers = listOf(
            ApiLayer("fundamental", 4, emptyList()),
            ApiLayer("sfs", 100, listOf(ApiSeries("act", 48), ApiSeries("ordinance", 50), ApiSeries("other_statute", 2))),
        ),
    )

    @Test
    fun countSumsLayers() {
        assertEquals(102, index.count(Scope.Nationell))
    }

    @Test
    fun regionAndKommunCountZero() {
        assertEquals(0, index.count(Scope.Region))
        assertEquals(0, index.count(Scope.Kommun))
    }

    private fun item(type: String, region: String?, kommun: String?) =
        ListingItem("x", "T", "1", type, null, null, regionCode = region, municipalityCode = kommun)

    @Test
    fun localityCodeAndLayerFollowTheScope() {
        val locality = Locality("01", "0180")
        assertEquals(null, Scope.Nationell.localityCode(locality))
        assertEquals("01", Scope.Region.localityCode(locality))
        assertEquals("0180", Scope.Kommun.localityCode(locality))
        assertEquals(DisplayLayer.Region, Scope.Region.localityLayer)
        assertEquals(DisplayLayer.Municipality, Scope.Kommun.localityLayer)
        assertEquals(null, Scope.Nationell.localityLayer)
    }

    @Test
    fun coversLocalityMatchesTheChosenCode() {
        val stockholm = Locality("01", "0180")
        val county = item("county_regulation", "01", null)
        val kommun = item("municipal_regulation", "01", "0180")
        assertTrue(Scope.Region.coversLocality(county, stockholm))
        assertFalse(Scope.Region.coversLocality(county, Locality("12", null)))
        assertTrue(Scope.Kommun.coversLocality(kommun, stockholm))
        assertFalse(Scope.Kommun.coversLocality(kommun, Locality("14", "1480")))
        // Nothing matches while no locality is chosen, and Nationell ignores it.
        assertFalse(Scope.Region.coversLocality(county, Locality(null, null)))
        assertFalse(Scope.Kommun.coversLocality(item("municipal_regulation", null, null), Locality(null, null)))
        assertTrue(Scope.Nationell.coversLocality(item("act", null, null), Locality(null, null)))
    }
}
