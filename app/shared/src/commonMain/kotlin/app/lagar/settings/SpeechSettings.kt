package app.lagar.settings

/**
 * How the reader reads a law aloud, chosen by the person listening and kept on the device. [voiceId] is the platform's
 * id of a Swedish voice, or null for the platform's default Swedish voice. [rate], [pitch] and [volume] are percent of
 * the platform's normal, in whole steps so they store and compare exactly.
 */
data class SpeechSettings(
    val voiceId: String? = null,
    val rate: Int = DEFAULT,
    val pitch: Int = DEFAULT,
    val volume: Int = MAX_VOLUME,
) {
    /** The same settings with every number brought into its range and onto its step. */
    fun normalized(): SpeechSettings = copy(
        rate = (rate.coerceIn(MIN_RATE, MAX_RATE) / STEP) * STEP,
        pitch = (pitch.coerceIn(MIN_PITCH, MAX_PITCH) / STEP) * STEP,
        volume = (volume.coerceIn(MIN_VOLUME, MAX_VOLUME) / STEP) * STEP,
    )

    val isDefault: Boolean get() = this == SpeechSettings()

    companion object {
        const val DEFAULT = 100
        const val STEP = 10
        const val MIN_RATE = 50
        const val MAX_RATE = 200
        const val MIN_PITCH = 50
        const val MAX_PITCH = 200
        const val MIN_VOLUME = 10
        const val MAX_VOLUME = 100
    }
}
