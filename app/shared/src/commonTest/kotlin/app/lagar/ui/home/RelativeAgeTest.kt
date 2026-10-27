package app.lagar.ui.home

import kotlinx.datetime.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals

class RelativeAgeTest {
    private val today = LocalDate(2026, 10, 27)

    private fun age(issued: String) = ageOf(LocalDate.parse(issued), today)

    @Test
    fun sameDayIsToday() = assertEquals(Age.Today, age("2026-10-27"))

    @Test
    fun dayBeforeIsYesterday() = assertEquals(Age.Yesterday, age("2026-10-26"))

    @Test
    fun lessThanAMonthCountsDays() = assertEquals(Age.Days(3), age("2026-10-24"))

    @Test
    fun monthsCountWholeMonths() {
        assertEquals(Age.Months(1), age("2026-09-27"))
        assertEquals(Age.Months(4), age("2026-06-11"))
    }

    @Test
    fun yearsCountWholeYears() {
        assertEquals(Age.Years(1), age("2025-10-27"))
        assertEquals(Age.Years(52), age("1974-02-28"))
    }

    @Test
    fun futureDateIsToday() = assertEquals(Age.Today, age("2026-12-01"))
}
