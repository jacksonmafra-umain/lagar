package app.lagar.speech

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import app.lagar.settings.SpeechSettings
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import platform.AVFAudio.AVAudioSession
import platform.AVFAudio.AVAudioSessionCategoryPlayback
import platform.AVFAudio.AVAudioSessionModeSpokenAudio
import platform.AVFAudio.AVSpeechBoundary
import platform.AVFAudio.AVSpeechSynthesisVoice
import platform.AVFAudio.AVSpeechSynthesizer
import platform.AVFAudio.AVSpeechSynthesizerDelegateProtocol
import platform.AVFAudio.AVSpeechUtterance
import platform.AVFAudio.AVSpeechUtteranceDefaultSpeechRate
import platform.AVFAudio.AVSpeechUtteranceMaximumSpeechRate
import platform.AVFAudio.AVSpeechUtteranceMinimumSpeechRate
import platform.AVFAudio.setActive
import platform.darwin.NSObject

/** Tells the engine when an utterance was spoken to the end; a stopped one is reported by [IosSpeechEngine.stop]. */
private class FinishDelegate(private val onFinish: (AVSpeechUtterance) -> Unit) :
    NSObject(),
    AVSpeechSynthesizerDelegateProtocol {
    override fun speechSynthesizer(synthesizer: AVSpeechSynthesizer, didFinishSpeechUtterance: AVSpeechUtterance) {
        onFinish(didFinishSpeechUtterance)
    }
}

/** `AVSpeechSynthesizer` with the Swedish voices installed on the device (Settings, Accessibility, Spoken Content). */
@OptIn(ExperimentalForeignApi::class)
private class IosSpeechEngine : SpeechEngine {
    private val synthesizer = AVSpeechSynthesizer()
    private var current: AVSpeechUtterance? = null
    private var pending: ((Boolean) -> Unit)? = null

    // The synthesizer holds its delegate weakly; this field keeps it alive.
    private val delegate = FinishDelegate { utterance ->
        if (utterance == current) {
            val done = pending
            pending = null
            current = null
            done?.invoke(true)
        }
    }

    override val voices: StateFlow<List<SpeechVoice>> = MutableStateFlow(
        AVSpeechSynthesisVoice.speechVoices()
            .filterIsInstance<AVSpeechSynthesisVoice>()
            .filter { isSwedish(it.language) }
            .map { SpeechVoice(it.identifier, it.name, it.language) },
    ).asStateFlow()

    init {
        synthesizer.delegate = delegate
    }

    override fun speak(text: String, settings: SpeechSettings, onDone: (finished: Boolean) -> Unit) {
        stop()
        // Spoken audio plays even with the ring/silent switch on, like a podcast app.
        AVAudioSession.sharedInstance().apply {
            setCategory(AVAudioSessionCategoryPlayback, mode = AVAudioSessionModeSpokenAudio, options = 0u, error = null)
            setActive(true, error = null)
        }
        val choice = voices.value.pick(settings.voiceId)
        val utterance = AVSpeechUtterance.speechUtteranceWithString(text).apply {
            voice = choice?.let { AVSpeechSynthesisVoice.voiceWithIdentifier(it.id) } ?: AVSpeechSynthesisVoice.voiceWithLanguage("sv-SE")
            rate = (AVSpeechUtteranceDefaultSpeechRate * settings.rate / 100f)
                .coerceIn(AVSpeechUtteranceMinimumSpeechRate, AVSpeechUtteranceMaximumSpeechRate)
            pitchMultiplier = settings.pitch / 100f
            volume = settings.volume / 100f
        }
        current = utterance
        pending = onDone
        synthesizer.speakUtterance(utterance)
    }

    override fun stop() {
        val done = pending
        pending = null
        current = null
        if (synthesizer.isSpeaking()) synthesizer.stopSpeakingAtBoundary(AVSpeechBoundary.AVSpeechBoundaryImmediate)
        done?.invoke(false)
    }

    override fun release() = stop()
}

@Composable
internal actual fun rememberSpeechEngine(): SpeechEngine {
    val engine = remember { IosSpeechEngine() }
    DisposableEffect(engine) { onDispose { engine.release() } }
    return engine
}
