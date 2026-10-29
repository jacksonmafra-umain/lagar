package app.lagar.ui.reader

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class ValidityMarkersTest {
    @Test
    fun expiringWordingWithCondition() {
        val result = statuteValidity(
            "**5 §** /Upphör att gälla U:den dag som regeringen bestämmer/ Fängelse är att anse som ett svårare straff än böter.",
        )
        assertEquals(ValidityMarker(ValidityChange.Expires, "den dag som regeringen bestämmer"), result.marker)
        assertEquals("**5 §** Fängelse är att anse som ett svårare straff än böter.", result.text)
    }

    @Test
    fun incomingWordingWithDate() {
        val result = statuteValidity(
            "**6 §** /Träder i kraft I:2031-09-10/ För brott som någon har begått innan han eller hon fyllt femton år. Lag (2026:1555).",
        )
        assertEquals(ValidityMarker(ValidityChange.EntersIntoForce, "2031-09-10"), result.marker)
        assertEquals("**6 §** För brott som någon har begått innan han eller hon fyllt femton år. Lag (2026:1555).", result.text)
    }

    @Test
    fun conditionNamingTheAmendmentDropsTheFinalStop() {
        val result = statuteValidity("**2 §** /Upphör att gälla U:2027-01-01 genom lag (2026:1244)./ Text.")
        assertEquals(ValidityMarker(ValidityChange.Expires, "2027-01-01 genom lag (2026:1244)"), result.marker)
        assertEquals("**2 §** Text.", result.text)
    }

    @Test
    fun letteredStatuteAndDoubledSlash() {
        val result = statuteValidity("**1 b §** //Upphör att gälla U:2028-10-01 genom lag (2024:562)./ Ett tillstånd.")
        assertEquals(ValidityMarker(ValidityChange.Expires, "2028-10-01 genom lag (2024:562)"), result.marker)
        assertEquals("**1 b §** Ett tillstånd.", result.text)
    }

    @Test
    fun laterLinesAreKept() {
        val result = statuteValidity("**3 §** /Träder i kraft I:2027-01-01/ Första stycket.\n\nAndra stycket.\n")
        assertEquals("**3 §** Första stycket.\n\nAndra stycket.\n", result.text)
    }

    @Test
    fun markerOnItsOwnLeavesTheNumber() {
        val result = statuteValidity("**4 §** /Träder i kraft I:2027-01-01/\n\nText.")
        assertEquals(ValidityMarker(ValidityChange.EntersIntoForce, "2027-01-01"), result.marker)
        assertEquals("**4 §**\n\nText.", result.text)
    }

    @Test
    fun plainStatuteIsUnchanged() {
        val block = "**1 §** All offentlig makt i Sverige utgår från folket."
        assertEquals(StatuteValidity(null, block), statuteValidity(block))
    }

    @Test
    fun markerLaterInTheTextIsLeftAlone() {
        val block = "**1 §** Text som nämner /Träder i kraft I:2027-01-01/ mitt i."
        assertNull(statuteValidity(block).marker)
        assertEquals(block, statuteValidity(block).text)
    }

    @Test
    fun otherSlashNotesAndUnclosedMarkersAreUnchanged() {
        listOf(
            "**8 §** /Ny beteckning 9 § U:2027-01-01/ Text.",
            "**2 §** /Upphör att gälla U:den dag som regeringen bestämmer Text utan slut.",
            "**2 §** /Upphör att gälla U:/ Text.",
            "## 1 kap. /Kapitlet träder i kraft I:2027-01-01/ Allmänt",
        ).forEach { block -> assertEquals(StatuteValidity(null, block), statuteValidity(block), block) }
    }
}
