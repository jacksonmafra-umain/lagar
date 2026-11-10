package app.lagar.speech

import app.lagar.settings.SpeechSettings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Where reading aloud stands: [active] while the player is shown, [item] the index of the text being read. */
data class ReadAloudState(val active: Boolean = false, val playing: Boolean = false, val item: Int = -1)

/**
 * Reads a list of texts (one per § or heading of a document) aloud with [engine], one after the other, each cut into
 * [speechChunks]. Blank texts are skipped. Pausing stops the engine and playing again starts the paused text from its
 * beginning, so it works the same on every platform. Call it from the main thread.
 */
class ReadAloud(private val engine: SpeechEngine, private val settings: () -> SpeechSettings) {
    private val _state = MutableStateFlow(ReadAloudState())
    val state: StateFlow<ReadAloudState> = _state.asStateFlow()

    private var items: List<String> = emptyList()
    private var chunks: List<String> = emptyList()
    private var chunk = 0

    // Each utterance carries the generation it was started in; a callback from an older one is ignored.
    private var generation = 0
    private var speaking = false

    /** Starts reading [items] at [from], or at the first non-blank text after it. */
    fun start(items: List<String>, from: Int) {
        this.items = items
        val first = nextNonBlank(from.coerceAtLeast(0)) ?: return
        play(first)
    }

    fun toggle() {
        val current = _state.value
        if (!current.active) return
        if (current.playing) {
            halt()
            _state.value = current.copy(playing = false)
        } else {
            play(current.item)
        }
    }

    fun next() {
        if (!_state.value.active) return
        nextNonBlank(_state.value.item + 1)?.let(::play)
    }

    fun previous() {
        if (!_state.value.active) return
        previousNonBlank(_state.value.item - 1)?.let(::play)
    }

    /** Applies new settings at once by starting the text being read again. */
    fun settingsChanged() {
        if (_state.value.playing) play(_state.value.item)
    }

    fun close() {
        halt()
        items = emptyList()
        _state.value = ReadAloudState()
    }

    private fun play(index: Int) {
        halt()
        chunks = speechChunks(items[index])
        chunk = 0
        _state.value = ReadAloudState(active = true, playing = true, item = index)
        speakChunk()
    }

    private fun speakChunk() {
        val current = ++generation
        speaking = true
        engine.speak(chunks[chunk], settings()) { finished ->
            if (current != generation) return@speak
            speaking = false
            if (finished) advance() else _state.value = _state.value.copy(playing = false)
        }
    }

    private fun advance() {
        chunk++
        if (chunk < chunks.size) {
            speakChunk()
            return
        }
        val next = nextNonBlank(_state.value.item + 1)
        if (next == null) _state.value = _state.value.copy(playing = false) else play(next)
    }

    private fun halt() {
        generation++
        if (speaking) {
            speaking = false
            engine.stop()
        }
    }

    private fun nextNonBlank(from: Int): Int? = (from until items.size).firstOrNull { items[it].isNotBlank() }

    private fun previousNonBlank(from: Int): Int? = (from downTo 0).firstOrNull { it < items.size && items[it].isNotBlank() }
}
