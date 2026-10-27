package app.lagar.i18n

import kotlin.test.Test
import kotlin.test.assertEquals

class SupportedLanguageTest {
    @Test
    fun swedishSystemTagResolvesToSwedish() {
        assertEquals(SupportedLanguage.Swedish, SupportedLanguage.resolve("sv-SE"))
    }

    @Test
    fun englishSystemTagResolvesToEnglish() {
        assertEquals(SupportedLanguage.English, SupportedLanguage.resolve("en-GB"))
        assertEquals(SupportedLanguage.English, SupportedLanguage.resolve("en_US"))
        assertEquals(SupportedLanguage.English, SupportedLanguage.resolve("en"))
    }

    @Test
    fun unsupportedSystemTagFallsBackToSwedish() {
        assertEquals(SupportedLanguage.Swedish, SupportedLanguage.resolve("de-DE"))
        assertEquals(SupportedLanguage.Swedish, SupportedLanguage.resolve(""))
    }

    @Test
    fun choiceResolvesExplicitlyOrFromSystem() {
        assertEquals(SupportedLanguage.Swedish, LanguageChoice.Swedish.resolve("en-US"))
        assertEquals(SupportedLanguage.English, LanguageChoice.English.resolve("de-DE"))
        assertEquals(SupportedLanguage.English, LanguageChoice.System.resolve("en-US"))
        assertEquals(SupportedLanguage.Swedish, LanguageChoice.System.resolve("de-DE"))
    }
}
