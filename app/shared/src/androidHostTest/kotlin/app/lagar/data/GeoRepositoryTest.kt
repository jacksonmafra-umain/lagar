package app.lagar.data

import app.lagar.domain.GeoPoint
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.nearestKommun
import kotlinx.coroutines.test.runTest
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class GeoRepositoryTest {
    // Compose resources are not available to JVM host tests, so read the bundled file from disk.
    private val repository = GeoRepository { path ->
        File("src/commonMain/composeResources/$path").readBytes()
    }

    @Test
    fun has21Regions() = runTest { assertEquals(21, repository.regions().size) }

    @Test
    fun has290Kommuner() = runTest {
        assertEquals(290, repository.regions().sumOf { repository.kommuner(it.code).size })
    }

    @Test
    fun kommunerFilteredByRegion() = runTest {
        val kommuner = repository.kommuner("14")
        assertTrue(kommuner.any { it.name == "Göteborg" })
        assertTrue(kommuner.all { it.regionCode == "14" })
    }

    @Test
    fun regionsUseSwedishCollation() = runTest {
        val names = repository.regions().map { it.name }
        assertEquals(listOf("Örebro län", "Östergötlands län"), names.takeLast(2))
        assertTrue(names.indexOf("Västra Götalands län") < names.indexOf("Örebro län"))
    }

    @Test
    fun nationalScopeHasNoLocalityName() = runTest {
        assertNull(repository.localityName(Scope.Nationell, Locality("14", "1480")))
    }

    @Test
    fun regionScopeNamesTheChosenRegion() = runTest {
        assertEquals("Västra Götalands län", repository.localityName(Scope.Region, Locality("14", null)))
        assertNull(repository.localityName(Scope.Region, Locality(null, null)))
    }

    @Test
    fun kommunScopeNamesTheChosenKommun() = runTest {
        assertEquals("Göteborg", repository.localityName(Scope.Kommun, Locality("14", "1480")))
        assertNull(repository.localityName(Scope.Kommun, Locality("14", null)))
        assertNull(repository.localityName(Scope.Kommun, Locality(null, "1480")))
    }

    @Test
    fun everyKommunHasACentroidInsideSweden() = runTest {
        val centroids = repository.centroids()
        assertEquals(290, centroids.size)
        assertTrue(centroids.all { it.center.lat in 55.0..69.1 && it.center.lon in 10.9..24.2 })
        assertTrue(centroids.all { it.radiusKm > 0 })
    }

    @Test
    fun centroidRegionsMatchTheKommunCodes() = runTest {
        val regionCodes = repository.regions().map { it.code }.toSet()
        repository.centroids().forEach {
            assertTrue(it.kommun.regionCode in regionCodes)
            assertEquals(it.kommun.regionCode, it.kommun.code.take(2))
        }
    }

    @Test
    fun cityCentresSuggestTheirKommun() = runTest {
        val centroids = repository.centroids()
        fun near(lat: Double, lon: Double) = nearestKommun(GeoPoint(lat, lon), centroids)?.kommun?.name
        assertEquals("Stockholm", near(59.3293, 18.0686))
        assertEquals("Göteborg", near(57.7089, 11.9746))
        assertEquals("Uppsala", near(59.8586, 17.6389))
        assertEquals("Kiruna", near(67.8558, 20.2253))
        assertEquals("Gotland", near(57.6348, 18.2948)) // Visby
    }

    @Test
    fun positionsAbroadSuggestNothing() = runTest {
        val centroids = repository.centroids()
        assertNull(nearestKommun(GeoPoint(59.9139, 10.7522), centroids)) // Oslo
        assertNull(nearestKommun(GeoPoint(52.52, 13.405), centroids)) // Berlin
    }
}
