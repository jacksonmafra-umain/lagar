package app.lagar.speech

import androidx.compose.runtime.Composable
import app.lagar.settings.SpeechSettings
import kotlinx.coroutines.flow.StateFlow

/** A voice the platform offers; [id] is stable on the device and is what [SpeechSettings.voiceId] stores. */
data class SpeechVoice(val id: String, val name: String, val language: String)

/**
 * The platform's own speech synthesis: the Web Speech API in a browser, `TextToSpeech` on Android and
 * `AVSpeechSynthesizer` on iOS. Nothing is generated or sent by the app; the platform voice speaks on the device (or
 * through the platform's own service).
 */
interface SpeechEngine {
    /** The Swedish voices installed; empty while the platform is still loading them, or when it has none. */
    val voices: StateFlow<List<SpeechVoice>>

    /**
     * Speaks [text] with [settings]. [onDone] runs once on the main thread: with `true` when the text was spoken to
     * the end, `false` when [stop] or an error cut it short.
     */
    fun speak(text: String, settings: SpeechSettings, onDone: (finished: Boolean) -> Unit)

    /** Stops speaking at once. */
    fun stop()

    /** Frees the platform engine; the instance is not used again. */
    fun release()
}

/** Whether a BCP 47 (`sv-SE`) or POSIX (`sv_SE`) language tag is Swedish. */
internal fun isSwedish(language: String): Boolean {
    val tag = language.replace('_', '-').lowercase()
    return tag == "sv" || tag.startsWith("sv-")
}

/** The voice [id] names when it is installed, else the first Swedish voice of Sweden, else the first one. */
internal fun List<SpeechVoice>.pick(id: String?): SpeechVoice? =
    firstOrNull { it.id == id } ?: firstOrNull { it.language.replace('_', '-').equals("sv-SE", ignoreCase = true) } ?: firstOrNull()

/** The platform's speech engine for as long as the calling screen is shown; it is released when the screen goes. */
@Composable
internal expect fun rememberSpeechEngine(): SpeechEngine
