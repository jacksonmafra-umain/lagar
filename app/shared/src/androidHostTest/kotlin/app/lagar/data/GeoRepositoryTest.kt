package app.lagar.data

import app.lagar.domain.Locality
import app.lagar.domain.Scope
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
}
