package app.lagar.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class NearestKommunTest {
    private val stockholm = KommunCentroid(Kommun("0180", "Stockholm", "01"), GeoPoint(59.323, 18.0), 15)
    private val solna = KommunCentroid(Kommun("0184", "Solna", "01"), GeoPoint(59.36, 17.999), 5)
    private val goteborg = KommunCentroid(Kommun("1480", "Göteborg", "14"), GeoPoint(57.744, 11.979), 21)
    private val kiruna = KommunCentroid(Kommun("2584", "Kiruna", "25"), GeoPoint(68.165, 20.737), 118)
    private val fixtures = listOf(stockholm, solna, goteborg, kiruna)

    @Test
    fun haversineMatchesKnownDistances() {
        assertEquals(0.0, haversineKm(GeoPoint(59.0, 18.0), GeoPoint(59.0, 18.0)))
        // One degree of latitude is about 111.2 km.
        assertEquals(111.2, haversineKm(GeoPoint(59.0, 18.0), GeoPoint(60.0, 18.0)), 0.1)
        // Stockholm to Göteborg is about 398 km along the great circle.
        assertEquals(398.0, haversineKm(GeoPoint(59.3293, 18.0686), GeoPoint(57.7089, 11.9746)), 3.0)
    }

    @Test
    fun picksTheNearestCentroid() {
        assertEquals(stockholm, nearestKommun(GeoPoint(59.3293, 18.0686), fixtures))
        assertEquals(solna, nearestKommun(GeoPoint(59.365, 18.0), fixtures))
        assertEquals(goteborg, nearestKommun(GeoPoint(57.7089, 11.9746), fixtures))
    }

    @Test
    fun largeKommunCoversItsFarCorners() {
        // Abisko is far from Kiruna's centroid but well inside its radius.
        assertEquals(kiruna, nearestKommun(GeoPoint(68.35, 18.83), fixtures))
    }

    @Test
    fun outsideEveryRadiusIsNoSuggestion() {
        assertNull(nearestKommun(GeoPoint(59.9139, 10.7522), fixtures)) // Oslo
        assertNull(nearestKommun(GeoPoint(0.0, 0.0), fixtures))
    }

    @Test
    fun noCentroidsIsNoSuggestion() {
        assertNull(nearestKommun(GeoPoint(59.3, 18.0), emptyList()))
    }

    @Test
    fun suggestionIsInTheKommunsRegion() {
        val nearest = nearestKommun(GeoPoint(57.7, 12.0), fixtures)
        assertTrue(nearest != null && nearest.kommun.regionCode == "14")
    }
}
