package app.lagar.speech

import app.lagar.settings.SpeechSettings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Records what it is asked to say; [finish] ends the utterance in progress as the platform would. */
private class FakeEngine : SpeechEngine {
    override val voices: StateFlow<List<SpeechVoice>> = MutableStateFlow(listOf(SpeechVoice("alva", "Alva", "sv-SE")))
    val spoken = mutableListOf<String>()
    val used = mutableListOf<SpeechSettings>()
    private var pending: ((Boolean) -> Unit)? = null
    var stops = 0

    override fun speak(text: String, settings: SpeechSettings, onDone: (finished: Boolean) -> Unit) {
        spoken += text
        used += settings
        pending = onDone
    }

    override fun stop() {
        stops++
        pending?.invoke(false)
        pending = null
    }

    override fun release() = Unit

    fun finish() {
        val done = pending
        pending = null
        done?.invoke(true)
    }
}

class ReadAloudTest {
    private val engine = FakeEngine()
    private var settings = SpeechSettings()
    private val reader = ReadAloud(engine) { settings }

    @Test
    fun readsFromTheGivenItemToTheEnd() {
        reader.start(listOf("Ett.", "Två.", "Tre."), from = 1)
        assertEquals(ReadAloudState(active = true, playing = true, item = 1), reader.state.value)
        engine.finish()
        assertEquals(2, reader.state.value.item)
        engine.finish()
        assertEquals(listOf("Två.", "Tre."), engine.spoken)
        assertFalse(reader.state.value.playing)
        assertTrue(reader.state.value.active, "the bar stays until it is closed")
    }

    @Test
    fun emptyItemsAreSkipped() {
        reader.start(listOf("Ett.", "", "  ", "Fyra."), from = 0)
        engine.finish()
        assertEquals(3, reader.state.value.item)
        assertEquals(listOf("Ett.", "Fyra."), engine.spoken)
    }

    @Test
    fun anItemIsSpokenInChunks() {
        val long = List(30) { "Detta är en mening." }.joinToString(" ")
        reader.start(listOf(long, "Nästa."), from = 0)
        while (reader.state.value.item == 0) engine.finish()
        assertTrue(engine.spoken.size > 2)
        assertEquals(long, engine.spoken.dropLast(1).joinToString(" "))
        assertEquals("Nästa.", engine.spoken.last())
    }

    @Test
    fun pauseStopsAndPlayRestartsTheSameItem() {
        reader.start(listOf("Ett.", "Två."), from = 0)
        engine.finish()
        reader.toggle()
        assertEquals(ReadAloudState(active = true, playing = false, item = 1), reader.state.value)
        assertEquals(1, engine.stops)
        reader.toggle()
        assertEquals(listOf("Ett.", "Två.", "Två."), engine.spoken)
        assertTrue(reader.state.value.playing)
    }

    @Test
    fun aStoppedUtteranceDoesNotAdvance() {
        reader.start(listOf("Ett.", "Två."), from = 0)
        reader.toggle()
        assertEquals(0, reader.state.value.item)
        assertEquals(listOf("Ett."), engine.spoken)
    }

    @Test
    fun nextAndPreviousMoveBetweenNonEmptyItems() {
        reader.start(listOf("Ett.", "", "Tre.", "Fyra."), from = 0)
        reader.next()
        assertEquals(2, reader.state.value.item)
        reader.next()
        reader.next()
        assertEquals(3, reader.state.value.item, "next stops at the last item")
        reader.previous()
        reader.previous()
        assertEquals(0, reader.state.value.item)
        assertEquals(listOf("Ett.", "Tre.", "Fyra.", "Tre.", "Ett."), engine.spoken)
    }

    @Test
    fun aSettingsChangeRestartsTheCurrentItemWithTheNewSettings() {
        reader.start(listOf("Ett."), from = 0)
        settings = SpeechSettings(rate = 150)
        reader.settingsChanged()
        assertEquals(listOf("Ett.", "Ett."), engine.spoken)
        assertEquals(150, engine.used.last().rate)
    }

    @Test
    fun closeStopsAndHidesTheBar() {
        reader.start(listOf("Ett.", "Två."), from = 0)
        reader.close()
        assertEquals(ReadAloudState(), reader.state.value)
        engine.finish()
        assertEquals(listOf("Ett."), engine.spoken)
    }
}
