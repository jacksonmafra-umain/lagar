package app.lagar.i18n

import kotlin.test.Test
import kotlin.test.assertEquals

class CountFormatTest {
    @Test
    fun swedishGroupsWithANoBreakSpace() {
        assertEquals("26 813", SupportedLanguage.Swedish.formatCount(26813))
        assertEquals("1 234 567", SupportedLanguage.Swedish.formatCount(1234567))
    }

    @Test
    fun englishGroupsWithAComma() {
        assertEquals("26,813", SupportedLanguage.English.formatCount(26813))
        assertEquals("1,234,567", SupportedLanguage.English.formatCount(1234567))
    }

    @Test
    fun shortCountsAreNotGrouped() {
        SupportedLanguage.entries.forEach { language ->
            assertEquals("0", language.formatCount(0))
            assertEquals("7", language.formatCount(7))
            assertEquals("999", language.formatCount(999))
        }
        assertEquals("1 000", SupportedLanguage.Swedish.formatCount(1000))
        assertEquals("1,000", SupportedLanguage.English.formatCount(1000))
    }

    @Test
    fun negativeAndLargeCountsKeepTheirSign() {
        assertEquals("-12,345", SupportedLanguage.English.formatCount(-12345))
        assertEquals("-999", SupportedLanguage.Swedish.formatCount(-999))
        assertEquals("2,147,483,647", SupportedLanguage.English.formatCount(Int.MAX_VALUE))
        assertEquals("-2,147,483,648", SupportedLanguage.English.formatCount(Int.MIN_VALUE))
    }
}
