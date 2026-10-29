package app.lagar.domain

import app.lagar.data.ListingItem
import kotlinx.datetime.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

class SearchTest {
    private fun item(
        id: String,
        title: String,
        number: String = "",
        type: String = "act",
        issued: String? = null,
        repealed: String? = null,
    ) = ListingItem(id, title, number, type, issued, repealed)

    private val skollag = item("a", "Skollag (2010:800)", "2010:800", issued = "2010-06-23")
    private val arbete = item("b", "Arbetsmiljölag", "1977:1160", issued = "1977-12-19", repealed = "2020-01-01")
    private val forordning = item("c", "Skolförordning", "2011:185", type = "ordinance", issued = "2011-03-10")
    private val agency = item("d", "Föreskrift om öar", "N2026:1", type = "regulation", issued = "2026-01-05")
    private val undated = item("e", "Skolplan", "2000:1")
    private val all = listOf(skollag, arbete, forordning, agency, undated)

    @Test
    fun matchesIgnoringCaseAndDiacritics() {
        assertEquals(listOf(arbete), all.search(SearchQuery("ARBETSMILJOLAG")))
        assertEquals(listOf(agency), all.search(SearchQuery("oar")))
        assertEquals(listOf(skollag, forordning, undated), all.search(SearchQuery("skol")))
        assertEquals(listOf(skollag), all.search(SearchQuery("skol lag")))
    }

    @Test
    fun numberModeMatchesNumberOnly() {
        assertEquals(listOf(skollag), all.search(SearchQuery("2010:800", mode = SearchMode.Number)))
        assertEquals(emptyList<ListingItem>(), all.search(SearchQuery("skollag", mode = SearchMode.Number)))
        assertEquals(listOf(agency), all.search(SearchQuery("n2026:1", mode = SearchMode.Number)))
        assertEquals(emptyList<ListingItem>(), all.search(SearchQuery("2026:1200", mode = SearchMode.Number)))
    }

    @Test
    fun typeFilter() {
        assertEquals(listOf(forordning), all.search(SearchQuery("skol", types = setOf("ordinance"))))
        assertEquals(listOf(forordning, agency), all.search(SearchQuery("", types = setOf("ordinance", "regulation"))))
    }

    @Test
    fun dateRangeInclusive() {
        val q = SearchQuery("skol", from = LocalDate(2010, 6, 23), to = LocalDate(2011, 3, 10))
        assertEquals(listOf(skollag, forordning), all.search(q))
        assertEquals(listOf(skollag), all.search(q.copy(to = LocalDate(2010, 6, 23))))
        assertEquals(listOf(skollag, forordning), all.search(SearchQuery("skol", from = LocalDate(2010, 1, 1))))
    }

    @Test
    fun invalidRangeIsRejected() {
        val q = SearchQuery("skol", from = LocalDate(2012, 1, 1), to = LocalDate(2010, 1, 1))
        assertFalse(q.isValidRange)
        assertEquals(emptyList<ListingItem>(), all.search(q))
    }

    @Test
    fun statusRepealedOnly() {
        assertEquals(listOf(arbete), all.search(SearchQuery("", status = StatusFilter.Repealed)))
        assertEquals(listOf(skollag), all.search(SearchQuery("skollag", status = StatusFilter.InForce)))
    }

    @Test
    fun blankQueryMatchesNothing() {
        assertEquals(emptyList<ListingItem>(), all.search(SearchQuery("")))
        assertEquals(emptyList<ListingItem>(), all.search(SearchQuery("   ")))
    }

    @Test
    fun noMatchReturnsEmpty() {
        assertEquals(emptyList<ListingItem>(), all.search(SearchQuery("zzz")))
    }

    @Test
    fun normalizeFoldsSwedishLettersAndDiacritics() {
        assertEquals("aao", normalize("ÅäÖ"))
        assertEquals("cafe", normalize("Café"))
    }

    private val today = LocalDate(2026, 10, 29)
    private val pending = item("f", "Lag om vindkraft", "2026:1113", issued = "2026-06-11").copy(inForce = "2027-01-01")
    private val started = item("g", "Lag om skatt", "2026:900", issued = "2026-05-02").copy(inForce = "2026-07-01")
    private val dated = listOf(skollag, pending, started)

    @Test
    fun inForceRangeSkipsDocumentsWithoutADate() {
        val q = SearchQuery("", inForceFrom = LocalDate(2026, 1, 1))
        assertEquals(listOf(pending, started), dated.search(q, today))
        assertEquals(listOf(started), dated.search(q.copy(inForceTo = LocalDate(2026, 7, 1)), today))
    }

    @Test
    fun vacatioLegisKeepsOnlyDocumentsNotYetInForce() {
        assertEquals(listOf(pending), dated.search(SearchQuery("", vacatioLegis = true), today))
        assertEquals(emptyList<ListingItem>(), dated.search(SearchQuery("", vacatioLegis = true), null))
    }

    @Test
    fun anInvertedInForceRangeIsRejected() {
        val q = SearchQuery("lag", inForceFrom = LocalDate(2027, 1, 1), inForceTo = LocalDate(2026, 1, 1))
        assertFalse(q.isValidRange)
        assertEquals(emptyList<ListingItem>(), dated.search(q, today))
    }

    @Test
    fun relevancePutsTitleMatchesBeforeNumberAndBodyOnlyMatches() {
        val body = SearchHit(item("x", "X", issued = "2030-01-01"), anyFields = SearchField.BODY, allFields = SearchField.BODY)
        val number = SearchHit(item("y", "Y", issued = "2029-01-01"), anyFields = SearchField.NUMBER, allFields = SearchField.NUMBER)
        val titleAndBody = SearchHit(item("z", "Z", issued = "1990-01-01"), anyFields = 5, allFields = 5)
        val title = SearchHit(item("w", "W", issued = "2000-01-01"), anyFields = SearchField.TITLE, allFields = SearchField.TITLE)
        val split = SearchHit(item("v", "V", issued = "2031-01-01"), anyFields = 5, allFields = 0)
        val sorted = listOf(body, number, split, title, titleAndBody).sortedFor(SortOrder.Relevance)
        assertEquals(listOf("z", "w", "y", "x", "v"), sorted.map { it.item.id })
    }

    @Test
    fun relevanceTiesGoNewestFirst() {
        val hits = all.searchHits(SearchQuery("skol")).sortedFor(SortOrder.Relevance)
        assertEquals(listOf(forordning, skollag, undated), hits.map { it.item })
    }

    @Test
    fun newestSortsUndatedLast() {
        val hits = all.searchHits(SearchQuery("", types = setOf("act"))).sortedFor(SortOrder.Newest)
        assertEquals(listOf(skollag, arbete, undated), hits.map { it.item })
    }

    @Test
    fun numberSortComparesYearAndOrdinalNumerically() {
        val items = listOf(
            item("1", "a", "1999:99"),
            item("2", "b", "1999:175"),
            item("3", "c", "N1999:5"),
            item("4", "d", "AFS 2023:1"),
            item("5", "e", "lokal"),
            item("6", "f", "1962:700"),
        )
        val hits = items.map { SearchHit(it) }.sortedFor(SortOrder.Number)
        assertEquals(listOf("6", "3", "1", "2", "4", "5"), hits.map { it.item.id })
    }

    @Test
    fun numberKeyReadsSfsAndSeriesNumbers() {
        assertEquals(1999 to 175L, numberKey("1999:175"))
        assertEquals(2026 to 1L, numberKey("N2026:1"))
        assertEquals(2016 to 40L, numberKey("HSLF-FS 2016:40"))
        assertEquals(2024 to 12L, numberKey("SKFS 2024:12"))
        assertEquals(null, numberKey("lokal"))
    }

    @Test
    fun catalogHitsRecordTheMatchedFields() {
        val hit = all.searchHits(SearchQuery("2010:800")).single()
        assertEquals(SearchField.TITLE or SearchField.NUMBER, hit.anyFields)
        assertEquals(SearchField.TITLE, all.searchHits(SearchQuery("skollag")).single().allFields)
    }

    @Test
    fun highlightsMarkWholeWordsAccentInsensitively() {
        val title = "Lag (2026:1113) om intäktsdelning från Åre"
        val marked = highlightRanges(title, "INTAKT are").map { title.substring(it) }
        assertEquals(listOf("intäktsdelning", "Åre"), marked)
        assertEquals(listOf("2026:1113"), highlightRanges(title, "2026:1113").map { title.substring(it) })
        assertEquals(emptyList(), highlightRanges(title, "om "))
    }
}
