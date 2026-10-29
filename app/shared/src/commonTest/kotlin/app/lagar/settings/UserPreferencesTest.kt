package app.lagar.settings

import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.i18n.LanguageChoice
import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class UserPreferencesTest {
    @Test
    fun defaultsToSystem() {
        val prefs = UserPreferences(MapSettings())
        assertEquals(LanguageChoice.System, prefs.language.value)
        assertEquals(ThemeMode.System, prefs.theme.value)
        assertEquals(ReduceTransparency.System, prefs.reduceTransparency.value)
    }

    @Test
    fun valuesPersistAcrossInstances() {
        val settings = MapSettings()
        val prefs = UserPreferences(settings)
        prefs.setLanguage(LanguageChoice.English)
        prefs.setTheme(ThemeMode.Dark)
        prefs.setReduceTransparency(ReduceTransparency.On)
        assertEquals(LanguageChoice.English, prefs.language.value)
        assertEquals(ThemeMode.Dark, prefs.theme.value)

        val reopened = UserPreferences(settings)
        assertEquals(LanguageChoice.English, reopened.language.value)
        assertEquals(ThemeMode.Dark, reopened.theme.value)
        assertEquals(ReduceTransparency.On, reopened.reduceTransparency.value)
    }

    @Test
    fun unknownStoredValueFallsBackToSystem() {
        val settings = MapSettings("language" to "klingon", "theme" to "neon", "reduce_transparency" to "sometimes")
        val prefs = UserPreferences(settings)
        assertEquals(LanguageChoice.System, prefs.language.value)
        assertEquals(ThemeMode.System, prefs.theme.value)
        assertEquals(ReduceTransparency.System, prefs.reduceTransparency.value)
    }

    @Test
    fun onboardingNotDoneUntilCompleted() {
        val prefs = UserPreferences(MapSettings())
        assertFalse(prefs.onboardingDone.value)
        assertEquals(Scope.Nationell, prefs.scope.value)
        assertEquals(Locality(null, null), prefs.locality.value)
    }

    @Test
    fun completeOnboardingPersists() {
        val settings = MapSettings()
        UserPreferences(settings).completeOnboarding(Scope.Kommun, Locality("14", "1480"))
        val reopened = UserPreferences(settings)
        assertTrue(reopened.onboardingDone.value)
        assertEquals(Scope.Kommun, reopened.scope.value)
        assertEquals(Locality("14", "1480"), reopened.locality.value)
    }

    @Test
    fun focusDefaultsToCitizen() {
        assertEquals(UserFocus.Citizen, UserPreferences(MapSettings()).focus.value)
        assertEquals(UserFocus.Citizen, UserPreferences(MapSettings("focus" to "astronaut")).focus.value)
    }

    @Test
    fun completeOnboardingStoresFocus() {
        val settings = MapSettings()
        UserPreferences(settings).completeOnboarding(Scope.Nationell, Locality(null, null), UserFocus.Student)
        assertEquals(UserFocus.Student, UserPreferences(settings).focus.value)
    }

    @Test
    fun setFocusPersistsImmediately() {
        val settings = MapSettings()
        val prefs = UserPreferences(settings)
        prefs.setFocus(UserFocus.Lawyer)
        assertEquals(UserFocus.Lawyer, prefs.focus.value)
        assertEquals(UserFocus.Lawyer, UserPreferences(settings).focus.value)
    }

    @Test
    fun setScopePersistsImmediately() {
        val settings = MapSettings()
        UserPreferences(settings).setScope(Scope.Region)
        assertEquals(Scope.Region, UserPreferences(settings).scope.value)
    }

    @Test
    fun changingRegionClearsKommun() {
        val prefs = UserPreferences(MapSettings())
        prefs.setRegion("14")
        prefs.setKommun("1480")
        prefs.setRegion("14")
        assertEquals(Locality("14", "1480"), prefs.locality.value)
        prefs.setRegion("01")
        assertEquals(Locality("01", null), prefs.locality.value)
        prefs.setKommun("0114")
        prefs.setRegion(null)
        assertEquals(Locality(null, null), prefs.locality.value)
    }
}
