package app.lagar.speech

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import app.lagar.settings.SpeechSettings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

private fun hasSpeech(): Boolean =
    js("typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance === 'function'")

// One voice per line: voiceURI, name and language separated by tabs.
private fun voiceLines(): String =
    js("speechSynthesis.getVoices().map(function (v) { return [v.voiceURI, v.name, v.lang].join('\\t'); }).join('\\n')")

// Chrome loads its voices after the page; the list is read again when they arrive.
private fun onVoicesChanged(callback: () -> Unit): Unit = js("speechSynthesis.onvoiceschanged = function () { callback(); }")

private fun speakText(text: String, voiceUri: String?, lang: String, rate: Double, pitch: Double, volume: Double, onEnd: (Boolean) -> Unit): Unit = js(
    """{
    var u = new SpeechSynthesisUtterance(text);
    var v = voiceUri ? speechSynthesis.getVoices().find(function (x) { return x.voiceURI === voiceUri; }) : null;
    if (v) u.voice = v;
    u.lang = v ? v.lang : lang;
    u.rate = rate;
    u.pitch = pitch;
    u.volume = volume;
    u.onend = function () { onEnd(true); };
    u.onerror = function () { onEnd(false); };
    speechSynthesis.speak(u);
    }""",
)

private fun cancelSpeech(): Unit = js("speechSynthesis.cancel()")

/** The Web Speech API's `speechSynthesis`, with the browser's or the system's Swedish voices. */
private class WebSpeechEngine : SpeechEngine {
    private val available = hasSpeech()
    private val _voices = MutableStateFlow(readVoices())
    override val voices: StateFlow<List<SpeechVoice>> = _voices.asStateFlow()

    init {
        if (available) onVoicesChanged { _voices.value = readVoices() }
    }

    private fun readVoices(): List<SpeechVoice> {
        if (!available) return emptyList()
        return voiceLines().lines().mapNotNull { line ->
            val parts = line.split('\t')
            if (parts.size == 3 && isSwedish(parts[2])) SpeechVoice(parts[0], parts[1], parts[2]) else null
        }
    }

    override fun speak(text: String, settings: SpeechSettings, onDone: (finished: Boolean) -> Unit) {
        if (!available) return onDone(false)
        val voice = _voices.value.pick(settings.voiceId)
        speakText(
            text = text,
            voiceUri = voice?.id,
            lang = voice?.language ?: "sv-SE",
            rate = settings.rate / 100.0,
            pitch = settings.pitch / 100.0,
            volume = settings.volume / 100.0,
            onEnd = onDone,
        )
    }

    override fun stop() {
        if (available) cancelSpeech()
    }

    override fun release() = stop()
}

@Composable
internal actual fun rememberSpeechEngine(): SpeechEngine {
    val engine = remember { WebSpeechEngine() }
    DisposableEffect(engine) { onDispose { engine.release() } }
    return engine
}
