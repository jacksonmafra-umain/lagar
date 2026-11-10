package app.lagar.settings

import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class SpeechPreferencesTest {
    @Test
    fun startsWithThePlatformVoiceAtNormalSpeedPitchAndVolume() {
        val settings = SpeechPreferences(MapSettings()).current.value
        assertTrue(settings.isDefault)
        assertNull(settings.voiceId)
        assertEquals(100, settings.rate)
        assertEquals(100, settings.pitch)
        assertEquals(100, settings.volume)
    }

    @Test
    fun savesAChangeAndReadsItBack() {
        val store = MapSettings()
        SpeechPreferences(store).update { it.copy(voiceId = "sv-SE-alva", rate = 130, pitch = 80, volume = 60) }
        val reloaded = SpeechPreferences(store).current.value
        assertEquals("sv-SE-alva", reloaded.voiceId)
        assertEquals(130, reloaded.rate)
        assertEquals(80, reloaded.pitch)
        assertEquals(60, reloaded.volume)
    }

    @Test
    fun keepsNumbersInRangeAndOnTheirStep() {
        val prefs = SpeechPreferences(MapSettings())
        prefs.update { it.copy(rate = 999, pitch = 1, volume = 0) }
        assertEquals(SpeechSettings.MAX_RATE, prefs.current.value.rate)
        assertEquals(SpeechSettings.MIN_PITCH, prefs.current.value.pitch)
        assertEquals(SpeechSettings.MIN_VOLUME, prefs.current.value.volume)
        prefs.update { it.copy(rate = 117) }
        assertEquals(110, prefs.current.value.rate)
    }

    @Test
    fun resetForgetsTheVoiceToo() {
        val store = MapSettings()
        val prefs = SpeechPreferences(store)
        prefs.update { it.copy(voiceId = "x", rate = 150) }
        prefs.reset()
        assertTrue(prefs.current.value.isDefault)
        assertNull(store.getStringOrNull("speech_voice"))
        assertTrue(SpeechPreferences(store).current.value.isDefault)
    }
}
