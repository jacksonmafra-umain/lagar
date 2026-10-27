package app.lagar.settings

import app.lagar.i18n.LanguageChoice
import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals

class UserPreferencesTest {
    @Test
    fun defaultsToSystem() {
        val prefs = UserPreferences(MapSettings())
        assertEquals(LanguageChoice.System, prefs.language.value)
        assertEquals(ThemeMode.System, prefs.theme.value)
    }

    @Test
    fun valuesPersistAcrossInstances() {
        val settings = MapSettings()
        val prefs = UserPreferences(settings)
        prefs.setLanguage(LanguageChoice.English)
        prefs.setTheme(ThemeMode.Dark)
        assertEquals(LanguageChoice.English, prefs.language.value)
        assertEquals(ThemeMode.Dark, prefs.theme.value)

        val reopened = UserPreferences(settings)
        assertEquals(LanguageChoice.English, reopened.language.value)
        assertEquals(ThemeMode.Dark, reopened.theme.value)
    }

    @Test
    fun unknownStoredValueFallsBackToSystem() {
        val settings = MapSettings("language" to "klingon", "theme" to "neon")
        val prefs = UserPreferences(settings)
        assertEquals(LanguageChoice.System, prefs.language.value)
        assertEquals(ThemeMode.System, prefs.theme.value)
    }
}
