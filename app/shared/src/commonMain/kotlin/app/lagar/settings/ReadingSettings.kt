package app.lagar.settings

/** The surface the reader draws its text on; [App] follows the app theme, the others are fixed papers. */
enum class ReadingPaper { App, Light, Sepia, Dark, HighContrast }

/** The family of the running legal text: the serif of DESIGN.md or the UI sans. */
enum class ReadingFont { Serif, Sans }

/** How wide a line of text may get, from the 60-75 character measure of DESIGN.md. */
enum class ReadingWidth { Narrow, Standard, Wide }

enum class ReadingAlign { Start, Justify }

/**
 * How the reader sets a legal text, chosen by the person reading and kept on the device. Numbers are whole steps so
 * they store and compare exactly: [textScale] in percent of the design size, [lineHeight] in tenths of the font size,
 * [letterSpacing] as a level from 0 (as designed) to [MAX_LETTER_SPACING].
 */
data class ReadingSettings(
    val paper: ReadingPaper = ReadingPaper.App,
    val font: ReadingFont = ReadingFont.Serif,
    val textScale: Int = DEFAULT_TEXT_SCALE,
    val lineHeight: Int = DEFAULT_LINE_HEIGHT,
    val letterSpacing: Int = 0,
    val width: ReadingWidth = ReadingWidth.Standard,
    val align: ReadingAlign = ReadingAlign.Start,
    val bold: Boolean = false,
) {
    /** The same settings with every number brought into its range and onto its step. */
    fun normalized(): ReadingSettings = copy(
        textScale = (textScale.coerceIn(MIN_TEXT_SCALE, MAX_TEXT_SCALE) / TEXT_SCALE_STEP) * TEXT_SCALE_STEP,
        lineHeight = lineHeight.coerceIn(MIN_LINE_HEIGHT, MAX_LINE_HEIGHT),
        letterSpacing = letterSpacing.coerceIn(0, MAX_LETTER_SPACING),
    )

    val isDefault: Boolean get() = this == ReadingSettings()

    companion object {
        const val MIN_TEXT_SCALE = 80
        const val MAX_TEXT_SCALE = 200
        const val TEXT_SCALE_STEP = 10
        const val DEFAULT_TEXT_SCALE = 100
        const val MIN_LINE_HEIGHT = 12
        const val MAX_LINE_HEIGHT = 22
        const val DEFAULT_LINE_HEIGHT = 16
        const val MAX_LETTER_SPACING = 3
    }
}
