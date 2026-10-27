package app.lagar.ui.home

import kotlinx.datetime.DateTimeUnit
import kotlinx.datetime.LocalDate
import kotlinx.datetime.until

/** How long ago a document was issued, in the coarsest unit that is at least one. */
internal sealed interface Age {
    data object Today : Age
    data object Yesterday : Age
    data class Days(val n: Int) : Age
    data class Months(val n: Int) : Age
    data class Years(val n: Int) : Age
}

internal fun ageOf(issued: LocalDate, today: LocalDate): Age {
    val years = issued.until(today, DateTimeUnit.YEAR).toInt()
    if (years >= 1) return Age.Years(years)
    val months = issued.until(today, DateTimeUnit.MONTH).toInt()
    if (months >= 1) return Age.Months(months)
    return when (val days = issued.until(today, DateTimeUnit.DAY).toInt()) {
        in Int.MIN_VALUE..0 -> Age.Today
        1 -> Age.Yesterday
        else -> Age.Days(days)
    }
}
