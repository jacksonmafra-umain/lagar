package app.lagar.speech

import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import app.lagar.settings.SpeechSettings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap

private val SWEDISH = Locale.forLanguageTag("sv-SE")

/** The id of the engine's own Swedish voice, used when it lists no Swedish [Voice] but can still speak Swedish. */
private const val DEFAULT_VOICE = "sv-SE"

/** Android's `TextToSpeech` with the default engine (Google's on most devices); callbacks arrive on the main thread. */
private class AndroidSpeechEngine(context: Context) : SpeechEngine {
    private val main = Handler(Looper.getMainLooper())
    private val callbacks = ConcurrentHashMap<String, (Boolean) -> Unit>()
    private val _voices = MutableStateFlow<List<SpeechVoice>>(emptyList())
    override val voices: StateFlow<List<SpeechVoice>> = _voices.asStateFlow()
    private var ready = false
    private var released = false
    private var nextId = 0
    private val tts = TextToSpeech(context.applicationContext) { status -> main.post { onInit(status) } }

    private fun onInit(status: Int) {
        if (released || status != TextToSpeech.SUCCESS) return
        ready = true
        tts.setOnUtteranceProgressListener(
            object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String) = Unit

                override fun onDone(utteranceId: String) = finish(utteranceId, true)

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String) = finish(utteranceId, false)

                override fun onError(utteranceId: String, errorCode: Int) = finish(utteranceId, false)

                override fun onStop(utteranceId: String, interrupted: Boolean) = finish(utteranceId, false)
            },
        )
        val installed = tts.voices.orEmpty()
            .filter { isSwedish(it.locale.toLanguageTag()) && TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED !in it.features }
            .sortedWith(compareBy<Voice> { it.isNetworkConnectionRequired }.thenBy { it.name })
            .map { SpeechVoice(it.name, voiceName(it), it.locale.toLanguageTag()) }
        _voices.value = when {
            installed.isNotEmpty() -> installed
            tts.isLanguageAvailable(SWEDISH) >= TextToSpeech.LANG_AVAILABLE -> listOf(SpeechVoice(DEFAULT_VOICE, "Svenska", "sv-SE"))
            else -> emptyList()
        }
    }

    /** A readable name: the language in Swedish and the engine's short name for the voice, "(online)" if it needs a network. */
    private fun voiceName(voice: Voice): String {
        val variant = voice.name.substringAfter("-x-", "").substringBefore('-').ifEmpty { voice.name }
        val online = if (voice.isNetworkConnectionRequired) " (online)" else ""
        return "${voice.locale.getDisplayName(SWEDISH).replaceFirstChar { it.uppercase() }} · $variant$online"
    }

    private fun finish(utteranceId: String, finished: Boolean) {
        val callback = callbacks.remove(utteranceId) ?: return
        main.post { callback(finished) }
    }

    override fun speak(text: String, settings: SpeechSettings, onDone: (finished: Boolean) -> Unit) {
        if (!ready || released) return onDone(false)
        val choice = _voices.value.pick(settings.voiceId)
        val voice = tts.voices.orEmpty().firstOrNull { it.name == choice?.id }
        if (voice != null) tts.voice = voice else tts.language = SWEDISH
        tts.setSpeechRate(settings.rate / 100f)
        tts.setPitch(settings.pitch / 100f)
        val params = Bundle().apply { putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, settings.volume / 100f) }
        val id = "lagar-${nextId++}"
        callbacks[id] = onDone
        if (tts.speak(text, TextToSpeech.QUEUE_FLUSH, params, id) != TextToSpeech.SUCCESS) finish(id, false)
    }

    override fun stop() {
        if (ready && !released) tts.stop()
    }

    override fun release() {
        released = true
        callbacks.clear()
        tts.stop()
        tts.shutdown()
    }
}

@Composable
internal actual fun rememberSpeechEngine(): SpeechEngine {
    val context = LocalContext.current
    val engine = remember(context) { AndroidSpeechEngine(context) }
    DisposableEffect(engine) { onDispose { engine.release() } }
    return engine
}
