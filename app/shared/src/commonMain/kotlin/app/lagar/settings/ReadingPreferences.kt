package app.lagar.settings

import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Device-local reading settings; a missing or unknown stored value falls back to the default. */
class ReadingPreferences(private val settings: Settings) {
    private val state = MutableStateFlow(load())

    val current: StateFlow<ReadingSettings> = state.asStateFlow()

    fun update(change: (ReadingSettings) -> ReadingSettings) {
        val next = change(state.value).normalized()
        write(next)
        state.value = next
    }

    fun reset() = update { ReadingSettings() }

    private fun load(): ReadingSettings {
        val d = ReadingSettings()
        return ReadingSettings(
            paper = read(KEY_PAPER, d.paper),
            font = read(KEY_FONT, d.font),
            textScale = settings.getInt(KEY_TEXT_SCALE, d.textScale),
            lineHeight = settings.getInt(KEY_LINE_HEIGHT, d.lineHeight),
            letterSpacing = settings.getInt(KEY_LETTER_SPACING, d.letterSpacing),
            width = read(KEY_WIDTH, d.width),
            align = read(KEY_ALIGN, d.align),
            bold = settings.getBoolean(KEY_BOLD, d.bold),
        ).normalized()
    }

    private fun write(value: ReadingSettings) {
        settings.putString(KEY_PAPER, value.paper.name)
        settings.putString(KEY_FONT, value.font.name)
        settings.putInt(KEY_TEXT_SCALE, value.textScale)
        settings.putInt(KEY_LINE_HEIGHT, value.lineHeight)
        settings.putInt(KEY_LETTER_SPACING, value.letterSpacing)
        settings.putString(KEY_WIDTH, value.width.name)
        settings.putString(KEY_ALIGN, value.align.name)
        settings.putBoolean(KEY_BOLD, value.bold)
    }

    private inline fun <reified E : Enum<E>> read(key: String, default: E): E {
        val stored = settings.getStringOrNull(key) ?: return default
        return enumValues<E>().firstOrNull { it.name == stored } ?: default
    }

    private companion object {
        const val KEY_PAPER = "reading_paper"
        const val KEY_FONT = "reading_font"
        const val KEY_TEXT_SCALE = "reading_text_scale"
        const val KEY_LINE_HEIGHT = "reading_line_height"
        const val KEY_LETTER_SPACING = "reading_letter_spacing"
        const val KEY_WIDTH = "reading_width"
        const val KEY_ALIGN = "reading_align"
        const val KEY_BOLD = "reading_bold"
    }
}
