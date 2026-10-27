package app.lagar.domain

import kotlin.test.Test
import kotlin.test.assertEquals

class LocalityTest {
    @Test
    fun changingRegionClearsKommun() {
        assertEquals(Locality("01", null), Locality("14", "1480").withRegion("01"))
    }

    @Test
    fun keepingRegionKeepsKommun() {
        assertEquals(Locality("14", "1480"), Locality("14", "1480").withRegion("14"))
    }

    @Test
    fun clearingRegionClearsKommun() {
        assertEquals(Locality(null, null), Locality("14", "1480").withRegion(null))
    }
}
