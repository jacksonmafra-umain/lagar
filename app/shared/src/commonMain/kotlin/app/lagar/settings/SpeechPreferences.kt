package app.lagar.settings

import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Device-local read-aloud settings; a missing stored value falls back to the default. */
class SpeechPreferences(private val settings: Settings) {
    private val state = MutableStateFlow(load())

    val current: StateFlow<SpeechSettings> = state.asStateFlow()

    fun update(change: (SpeechSettings) -> SpeechSettings) {
        val next = change(state.value).normalized()
        write(next)
        state.value = next
    }

    fun reset() = update { SpeechSettings() }

    private fun load(): SpeechSettings {
        val d = SpeechSettings()
        return SpeechSettings(
            voiceId = settings.getStringOrNull(KEY_VOICE),
            rate = settings.getInt(KEY_RATE, d.rate),
            pitch = settings.getInt(KEY_PITCH, d.pitch),
            volume = settings.getInt(KEY_VOLUME, d.volume),
        ).normalized()
    }

    private fun write(value: SpeechSettings) {
        val voice = value.voiceId
        if (voice == null) settings.remove(KEY_VOICE) else settings.putString(KEY_VOICE, voice)
        settings.putInt(KEY_RATE, value.rate)
        settings.putInt(KEY_PITCH, value.pitch)
        settings.putInt(KEY_VOLUME, value.volume)
    }

    private companion object {
        const val KEY_VOICE = "speech_voice"
        const val KEY_RATE = "speech_rate"
        const val KEY_PITCH = "speech_pitch"
        const val KEY_VOLUME = "speech_volume"
    }
}
