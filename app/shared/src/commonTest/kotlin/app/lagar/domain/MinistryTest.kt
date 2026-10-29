package app.lagar.domain

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class MinistryTest {
    @Test
    fun dropsTheUnitCodeAfterAMinistry() {
        assertEquals("Justitiedepartementet", ministryName("Justitiedepartementet L5"))
        assertEquals("Justitiedepartementet", ministryName("Justitiedepartementet DOM"))
        assertEquals("Klimat- och näringslivsdepartementet", ministryName("Klimat- och näringslivsdepartementet RS"))
    }

    @Test
    fun keepsAMinistryWithoutUnitCode() {
        assertEquals("Finansdepartementet", ministryName("Finansdepartementet"))
    }

    @Test
    fun collapsesWhitespace() {
        assertEquals("Justitiedepartementet", ministryName("  Justitiedepartementet \t L2 "))
        assertEquals("Statistiska centralbyrån", ministryName(" Statistiska   centralbyrån "))
    }

    @Test
    fun keepsOtherBodiesAsWritten() {
        assertEquals("Riksbanken", ministryName("Riksbanken"))
        assertEquals("Statsrådsberedningen SB", ministryName("Statsrådsberedningen SB"))
    }

    @Test
    fun blankIsNull() {
        assertNull(ministryName(null))
        assertNull(ministryName("   "))
    }
}
