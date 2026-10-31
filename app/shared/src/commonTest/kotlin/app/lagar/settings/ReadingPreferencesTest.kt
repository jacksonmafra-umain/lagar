package app.lagar.settings

import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ReadingPreferencesTest {
    @Test
    fun startsWithTheDesignDefaults() {
        assertTrue(ReadingPreferences(MapSettings()).current.value.isDefault)
    }

    @Test
    fun savesAChangeAndReadsItBack() {
        val store = MapSettings()
        ReadingPreferences(store).update { it.copy(paper = ReadingPaper.Sepia, textScale = 140, bold = true) }
        val reloaded = ReadingPreferences(store).current.value
        assertEquals(ReadingPaper.Sepia, reloaded.paper)
        assertEquals(140, reloaded.textScale)
        assertTrue(reloaded.bold)
    }

    @Test
    fun keepsNumbersInRangeAndOnTheirStep() {
        val prefs = ReadingPreferences(MapSettings())
        prefs.update { it.copy(textScale = 999, lineHeight = 1, letterSpacing = 9) }
        assertEquals(ReadingSettings.MAX_TEXT_SCALE, prefs.current.value.textScale)
        assertEquals(ReadingSettings.MIN_LINE_HEIGHT, prefs.current.value.lineHeight)
        assertEquals(ReadingSettings.MAX_LETTER_SPACING, prefs.current.value.letterSpacing)
        prefs.update { it.copy(textScale = 113) }
        assertEquals(110, prefs.current.value.textScale)
    }

    @Test
    fun anUnknownStoredValueFallsBackToTheDefault() {
        val store = MapSettings("reading_paper" to "Neon", "reading_text_scale" to 5)
        val loaded = ReadingPreferences(store).current.value
        assertEquals(ReadingPaper.App, loaded.paper)
        assertEquals(ReadingSettings.MIN_TEXT_SCALE, loaded.textScale)
    }

    @Test
    fun resetRestoresTheDefaults() {
        val prefs = ReadingPreferences(MapSettings())
        prefs.update { it.copy(font = ReadingFont.Sans, align = ReadingAlign.Justify) }
        prefs.reset()
        assertTrue(prefs.current.value.isDefault)
    }
}
