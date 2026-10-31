package app.lagar.ui.reader

import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp
import app.lagar.designsystem.LagarTypography
import app.lagar.settings.ReadingAlign
import app.lagar.settings.ReadingFont
import app.lagar.settings.ReadingPaper
import app.lagar.settings.ReadingSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class ReadingStyleTest {
    private val serif = TextStyle(fontFamily = FontFamily.Serif, fontSize = 16.sp, lineHeight = 26.sp)
    private val sans = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 15.sp, lineHeight = 22.sp)
    private val type = LagarTypography(
        displayLg = sans, displayLgMobile = sans, headlineLg = sans, headlineLgMobile = sans, headlineMd = sans,
        headlineSm = sans, statuteNum = sans, bodyLegalLg = serif, bodyLegalMd = serif, bodyUi = sans, labelMd = sans,
        labelSm = sans, codeCitation = sans,
    )

    @Test
    fun defaultSettingsKeepTheDesignScale() {
        assertSame(type, type.forReading(ReadingSettings()))
    }

    @Test
    fun textScaleGrowsTheLegalTextButNotTheChrome() {
        val scaled = type.forReading(ReadingSettings(textScale = 150))
        assertEquals(24.sp, scaled.bodyLegalMd.fontSize)
        assertEquals(39.sp, scaled.bodyLegalMd.lineHeight)
        assertEquals(22.5.sp, scaled.statuteNum.fontSize)
        assertEquals(15.sp, scaled.bodyUi.fontSize)
    }

    @Test
    fun lineHeightIsAMultipleOfTheFontSize() {
        assertEquals(32.sp, type.forReading(ReadingSettings(lineHeight = 20)).bodyLegalMd.lineHeight)
    }

    @Test
    fun sansBoldJustifiedText() {
        val body = type.forReading(ReadingSettings(font = ReadingFont.Sans, bold = true, align = ReadingAlign.Justify)).bodyLegalMd
        assertEquals(FontFamily.SansSerif, body.fontFamily)
        assertEquals(FontWeight.Bold, body.fontWeight)
        assertEquals(TextAlign.Justify, body.textAlign)
    }

    @Test
    fun paperDarknessFollowsTheAppOnlyWhereItShould() {
        assertTrue(ReadingPaper.Dark.isDark(appDark = false))
        assertFalse(ReadingPaper.Sepia.isDark(appDark = true))
        assertTrue(ReadingPaper.HighContrast.isDark(appDark = true))
        assertFalse(ReadingPaper.App.isDark(appDark = false))
    }
}
