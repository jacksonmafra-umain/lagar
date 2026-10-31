package app.lagar.ui.reader

import androidx.compose.material3.ColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.em
import app.lagar.designsystem.LagarSubtheme
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.LagarTypography
import app.lagar.designsystem.lagarDarkColorScheme
import app.lagar.designsystem.lagarLightColorScheme
import app.lagar.settings.ReadingAlign
import app.lagar.settings.ReadingFont
import app.lagar.settings.ReadingPaper
import app.lagar.settings.ReadingSettings
import app.lagar.settings.ReadingWidth

/** Extra letter spacing per step of [ReadingSettings.letterSpacing]. */
private const val LETTER_SPACING_STEP = 0.02f

/** The longest line of legal text for each column width, in characters; [ReadingWidth.Standard] is DESIGN.md's measure. */
internal fun ReadingWidth.lineChars(): Int = when (this) {
    ReadingWidth.Narrow -> 55
    ReadingWidth.Standard -> 70
    ReadingWidth.Wide -> 90
}

/** The reading measure in characters, read by [readingColumn]. */
internal val LocalReadingMeasure = staticCompositionLocalOf { ReadingWidth.Standard.lineChars() }

/**
 * The type scale with the legal text set as [settings] asks: size, family, line height, letter spacing, weight and
 * alignment for the body, size alone for the § numbers and headings. The UI chrome keeps the design sizes. Default
 * settings give the design scale back.
 */
internal fun LagarTypography.forReading(settings: ReadingSettings): LagarTypography {
    if (settings.isDefault) return this
    val scale = settings.textScale / 100f
    val family = if (settings.font == ReadingFont.Sans) bodyUi.fontFamily else bodyLegalMd.fontFamily

    fun TextStyle.scaled() = copy(fontSize = fontSize * scale, lineHeight = lineHeight * scale)

    fun TextStyle.body(): TextStyle {
        val size = fontSize * scale
        return copy(
            fontFamily = family,
            fontSize = size,
            // The default step keeps the design's own line height; the others are a multiple of the font size.
            lineHeight = if (settings.lineHeight == ReadingSettings.DEFAULT_LINE_HEIGHT) lineHeight * scale else size * (settings.lineHeight / 10f),
            letterSpacing = if (settings.letterSpacing == 0) letterSpacing else (settings.letterSpacing * LETTER_SPACING_STEP).em,
            fontWeight = if (settings.bold) FontWeight.Bold else fontWeight,
            textAlign = if (settings.align == ReadingAlign.Justify) TextAlign.Justify else TextAlign.Start,
        )
    }
    return LagarTypography(
        displayLg = displayLg,
        displayLgMobile = displayLgMobile,
        headlineLg = headlineLg,
        headlineLgMobile = headlineLgMobile,
        headlineMd = headlineMd.scaled(),
        headlineSm = headlineSm.scaled(),
        statuteNum = statuteNum.scaled(),
        bodyLegalLg = bodyLegalLg.body(),
        bodyLegalMd = bodyLegalMd.body(),
        bodyUi = bodyUi,
        labelMd = labelMd,
        labelSm = labelSm,
        codeCitation = codeCitation,
    )
}

private val SepiaPaper = Color(0xFFF4ECD8)
private val SepiaInk = Color(0xFF3B2E1E)

/** A warm paper: the light scheme with a sepia surface and brown ink (about 11:1, and 6:1 for the secondary text). */
private fun sepiaScheme(): ColorScheme = lagarLightColorScheme().copy(
    background = SepiaPaper,
    onBackground = SepiaInk,
    surface = SepiaPaper,
    onSurface = SepiaInk,
    onSurfaceVariant = Color(0xFF5E4C34),
    outlineVariant = Color(0xFFD8C9A8),
    surfaceContainerLowest = Color(0xFFF9F3E4),
    surfaceContainerLow = Color(0xFFEFE5CD),
    surfaceContainer = Color(0xFFEADFC4),
    surfaceContainerHigh = Color(0xFFE4D8BA),
    surfaceContainerHighest = Color(0xFFDED1B1),
)

/** Pure black on white, or white on black under a dark app theme, with secondary text and rules at full strength. */
private fun highContrastScheme(dark: Boolean): ColorScheme = if (dark) {
    lagarDarkColorScheme().copy(
        background = Color.Black,
        onBackground = Color.White,
        surface = Color.Black,
        onSurface = Color.White,
        onSurfaceVariant = Color(0xFFEDEDED),
        outlineVariant = Color(0xFF9E9E9E),
        surfaceContainerLowest = Color.Black,
        surfaceContainerLow = Color(0xFF0D0D0D),
        surfaceContainer = Color(0xFF141414),
        surfaceContainerHigh = Color(0xFF1C1C1C),
        surfaceContainerHighest = Color(0xFF262626),
    )
} else {
    lagarLightColorScheme().copy(
        background = Color.White,
        onBackground = Color.Black,
        surface = Color.White,
        onSurface = Color.Black,
        onSurfaceVariant = Color(0xFF1A1A1A),
        outlineVariant = Color(0xFF616161),
        surfaceContainerLowest = Color.White,
        surfaceContainerLow = Color(0xFFF5F5F5),
        surfaceContainer = Color(0xFFEFEFEF),
        surfaceContainerHigh = Color(0xFFE8E8E8),
        surfaceContainerHighest = Color(0xFFE0E0E0),
    )
}

/** Whether [paper] is dark, given whether the app theme is. */
internal fun ReadingPaper.isDark(appDark: Boolean): Boolean = when (this) {
    ReadingPaper.App, ReadingPaper.HighContrast -> appDark
    ReadingPaper.Light, ReadingPaper.Sepia -> false
    ReadingPaper.Dark -> true
}

/** Sets [content] on the paper, type and measure that [settings] asks for. */
@Composable
internal fun ReadingTheme(settings: ReadingSettings, content: @Composable () -> Unit) {
    val appDark = LagarTheme.isDark
    val appColors = LagarTheme.colors
    val dark = settings.paper.isDark(appDark)
    val colors = remember(settings.paper, appDark, appColors) {
        when (settings.paper) {
            ReadingPaper.App -> appColors
            ReadingPaper.Light -> lagarLightColorScheme()
            ReadingPaper.Sepia -> sepiaScheme()
            ReadingPaper.Dark -> lagarDarkColorScheme()
            ReadingPaper.HighContrast -> highContrastScheme(appDark)
        }
    }
    val appType = LagarTheme.type
    val type = remember(appType, settings) { appType.forReading(settings) }
    LagarSubtheme(colors = colors, type = type, darkTheme = dark) {
        CompositionLocalProvider(LocalReadingMeasure provides settings.width.lineChars(), content = content)
    }
}
