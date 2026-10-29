package app.lagar.ui.search

import app.lagar.data.ApiIndex
import app.lagar.data.ApiLayer
import app.lagar.data.ApiSeries
import app.lagar.domain.Scope
import kotlinx.datetime.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals

class DatesTest {
    @Test
    fun pickerMillisRoundTripAtUtcMidnight() {
        val date = LocalDate(1810, 9, 26)
        assertEquals(date, pickerMillisToDate(date.toPickerMillis()))
        assertEquals(0L, LocalDate(1970, 1, 1).toPickerMillis())
        assertEquals(LocalDate(2026, 10, 29), pickerMillisToDate(LocalDate(2026, 10, 29).toPickerMillis() + 3_600_000))
    }

    @Test
    fun monthNameUsesTheGivenNames() {
        val months = listOf("jan.", "feb.", "mars", "apr.", "maj", "juni", "juli", "aug.", "sep.", "okt.", "nov.", "dec.")
        assertEquals("okt.", monthName(LocalDate(2026, 10, 29), months))
        assertEquals("JANUARY", monthName(LocalDate(2026, 1, 1), emptyList()))
    }

    @Test
    fun pickerYearsReachTheOldestPrints() {
        assertEquals(true, 1736 in PickerYears)
    }

    @Test
    fun documentTypesFollowTheIndexSeriesOfTheScope() {
        val index = ApiIndex(
            1,
            "t",
            listOf(
                ApiLayer("fundamental", 4, listOf(ApiSeries("fundamental_law", 4))),
                ApiLayer("sfs", 3, listOf(ApiSeries("act", 2), ApiSeries("other_statute", 1))),
                ApiLayer("case_law", 1, listOf(ApiSeries("case_report", 1))),
                ApiLayer("eu", 0, emptyList()),
                ApiLayer("municipality", 2, listOf(ApiSeries("municipal_regulation", 2))),
            ),
        )
        assertEquals(listOf("fundamental_law", "act", "other_statute", "case_report"), index.documentTypes(Scope.Nationell))
        assertEquals(listOf("municipal_regulation"), index.documentTypes(Scope.Kommun))
        assertEquals(emptyList(), index.documentTypes(Scope.Region))
    }
}
