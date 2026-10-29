package app.lagar.ui.reader

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class CrossReferencesTest {
    private fun linked(text: String): List<Pair<String, String>> = findCitations(text).map { text.substring(it.start, it.end) to it.id }

    @Test
    fun linksAStatuteWordWithItsNumberInParentheses() {
        assertEquals(
            listOf("lagen (1977:654)" to "sfs-1977-654"),
            linked("- 1 § lagen (1977:654) om kungörande i mål och ärenden"),
        )
        assertEquals(listOf("brottsbalken (1962:700)" to "sfs-1962-700"), linked("6 § brottsbalken (1962:700)"))
        assertEquals(listOf("förordningen (2026:12)" to "sfs-2026-12"), linked("enligt förordningen (2026:12) om avgifter"))
    }

    @Test
    fun linksCompoundAndHyphenatedStatuteNames() {
        assertEquals(
            listOf("sekretesslagen (2009:400)" to "sfs-2009-400"),
            linked("7 § offentlighets- och sekretesslagen (2009:400)"),
        )
        assertEquals(listOf("regeringsformen (1974:152)" to "sfs-1974-152"), linked("enligt regeringsformen (1974:152)"))
    }

    @Test
    fun linksAmendmentNotes() {
        assertEquals(listOf("Lag (1994:458)" to "sfs-1994-458"), linked("som avser mindre belopp. Lag (1994:458)."))
        assertEquals(listOf("lag (2010:739)" to "sfs-2010-739"), linked("**34 §** Har upphävts genom lag (2010:739)."))
        assertEquals(listOf("Förordning 1995:908" to "sfs-1995-908"), linked("bostadslånet. Förordning 1995:908."))
    }

    @Test
    fun linksSfsPrefixedAndBareParenthesisedNumbers() {
        assertEquals(
            listOf("SFS 1967:663" to "sfs-1967-663", "SFS 2003:832" to "sfs-2003-832"),
            linked("ökas med 0,25 procent (jfr SFS 1967:663 och SFS 2003:832),"),
        )
        assertEquals(listOf("miljöbalken (SFS 1998:808)" to "sfs-1998-808"), linked("miljöbalken (SFS 1998:808)"))
        assertEquals(listOf("SFS 1998:808" to "sfs-1998-808"), linked("i texten (SFS 1998:808)"))
        assertEquals(listOf("2001:1063" to "sfs-2001-1063"), linked("enligt (2001:1063). Mer text"))
    }

    @Test
    fun linksNumbersAfterAStatuteWordWithoutParentheses() {
        assertEquals(listOf("lagen 1962:700" to "sfs-1962-700"), linked("se lagen 1962:700 om"))
    }

    @Test
    fun linksTheNSeries() {
        assertEquals(listOf("förordningen (N2019:2)" to "sfs-n2019-2"), linked("i förordningen (N2019:2) om"))
    }

    @Test
    fun linksOnlyTheFirstNumberWhenTheParenthesisGoesOn() {
        assertEquals(
            listOf("1968:473" to "sfs-1968-473"),
            linked("lagen (1968:473, ändr. och omtr. 1979:679) om tillämpning"),
        )
    }

    @Test
    fun leavesSectionReferencesAndOtherSeriesPlain() {
        assertTrue(findCitations("enligt 1 kap. 3 § och 2 kap. 4-6 §§ samma lag").isEmpty())
        assertTrue(findCitations("med främmande makter (SÖ 1987:87) i dess lydelse").isEmpty())
        assertTrue(findCitations("ingår i SÖ 1999:29, 1999:30 och 1999:31.").isEmpty())
        assertTrue(findCitations("föreskrifter (SKOLFS 2011:144) om läroplan").isEmpty())
        assertTrue(findCitations("se prop. 1975/76:31 s. 117 och SOU 2020:12").isEmpty())
        assertTrue(findCitations("publikationer 1963:2) och").isEmpty())
        assertTrue(findCitations("kl. 2026:12:30 och 12026:1").isEmpty())
    }

    @Test
    fun linksCaseLawReferences() {
        assertEquals(
            listOf("NJA 2026:38" to "nja-2026-38", "NJA 2026 s. 435" to "nja-2026-s-435"),
            linked("Referat: NJA 2026:38, NJA 2026 s. 435 p. 3"),
        )
        assertEquals(listOf("HFD 2015 ref. 9" to "hfd-2015-ref-9"), linked("(jfr prop. 1975/76:31 s. 117 och HFD 2015 ref. 9)."))
        assertEquals(listOf("HFD 2026 not. 24" to "hfd-2026-not-24"), linked("se HFD 2026 not. 24"))
        assertEquals(listOf("RÅ 2010 ref. 5" to "ra-2010-ref-5"), linked("se RÅ 2010 ref. 5"))
    }

    @Test
    fun caseLawIdsMatchTheCollectorSlug() {
        assertEquals("nja-2026-38", caseLawDocumentId("NJA 2026:38"))
        assertEquals("hfd-2026-ref-43", caseLawDocumentId("HFD 2026 ref. 43"))
        assertEquals("mod-2020-12", caseLawDocumentId("MÖD 2020:12"))
    }

    @Test
    fun keepsTextOrderAcrossKinds() {
        val text = "6 § brottsbalken (1962:700) och NJA 2026:38 samt Lag (1994:458)."
        assertEquals(listOf("sfs-1962-700", "nja-2026-38", "sfs-1994-458"), findCitations(text).map { it.id })
        assertEquals(setOf("sfs-1962-700", "nja-2026-38", "sfs-1994-458"), citedDocumentIds(text))
    }

    @Test
    fun rewritesOnlyKnownTargetsAsLinks() {
        val text = "enligt 4 § skadeståndslagen (1972:207) och lagen (1994:1219) om konventionen"
        assertEquals(
            "enligt 4 § [skadeståndslagen (1972:207)](lagar-doc:sfs-1972-207) och lagen (1994:1219) om konventionen",
            linkCitations(text, setOf("sfs-1972-207")),
        )
        assertEquals(text, linkCitations(text, emptySet()))
        assertEquals(text, linkCitations(text, setOf("sfs-2000-1")))
    }
}
