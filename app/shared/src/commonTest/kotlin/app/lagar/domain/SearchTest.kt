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
}
