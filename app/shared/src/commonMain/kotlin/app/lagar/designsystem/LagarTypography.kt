package app.lagar.designsystem

import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.remember
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import app.lagar.designsystem.generated.FontKey
import app.lagar.designsystem.generated.TextStyleSpec
import app.lagar.designsystem.generated.TypeTokens
import app.lagar.resources.Res
import app.lagar.resources.inter_bold
import app.lagar.resources.inter_medium
import app.lagar.resources.inter_regular
import app.lagar.resources.inter_semibold
import app.lagar.resources.source_serif_4_bold
import app.lagar.resources.source_serif_4_regular
import org.jetbrains.compose.resources.Font

@Immutable
class LagarTypography(
    val displayLg: TextStyle,
    val displayLgMobile: TextStyle,
    val headlineLg: TextStyle,
    val headlineLgMobile: TextStyle,
    val headlineMd: TextStyle,
    val headlineSm: TextStyle,
    val statuteNum: TextStyle,
    val bodyLegalLg: TextStyle,
    val bodyLegalMd: TextStyle,
    val bodyUi: TextStyle,
    val labelMd: TextStyle,
    val labelSm: TextStyle,
    val codeCitation: TextStyle,
)

@Composable
private fun interFamily(): FontFamily = FontFamily(
    Font(Res.font.inter_regular, FontWeight.Normal),
    Font(Res.font.inter_medium, FontWeight.Medium),
    Font(Res.font.inter_semibold, FontWeight.SemiBold),
    Font(Res.font.inter_bold, FontWeight.Bold),
)

@Composable
private fun sourceSerifFamily(): FontFamily = FontFamily(
    Font(Res.font.source_serif_4_regular, FontWeight.Normal),
    Font(Res.font.source_serif_4_bold, FontWeight.Bold),
)

private fun TextStyleSpec.toTextStyle(families: Map<FontKey, FontFamily>) = TextStyle(
    fontFamily = families.getValue(family),
    fontSize = sizeSp.sp,
    lineHeight = lineHeightSp.sp,
    fontWeight = FontWeight(weight),
    letterSpacing = letterSpacingEm.em,
)

@Composable
internal fun rememberLagarTypography(): LagarTypography {
    val inter = interFamily()
    val serif = sourceSerifFamily()
    return remember(inter, serif) {
        val families = mapOf(FontKey.Inter to inter, FontKey.SourceSerif4 to serif)
        with(TypeTokens) {
            LagarTypography(
                displayLg = displayLg.toTextStyle(families),
                displayLgMobile = displayLgMobile.toTextStyle(families),
                headlineLg = headlineLg.toTextStyle(families),
                headlineLgMobile = headlineLgMobile.toTextStyle(families),
                headlineMd = headlineMd.toTextStyle(families),
                headlineSm = headlineSm.toTextStyle(families),
                statuteNum = statuteNum.toTextStyle(families),
                bodyLegalLg = bodyLegalLg.toTextStyle(families),
                bodyLegalMd = bodyLegalMd.toTextStyle(families),
                bodyUi = bodyUi.toTextStyle(families),
                labelMd = labelMd.toTextStyle(families),
                labelSm = labelSm.toTextStyle(families),
                codeCitation = codeCitation.toTextStyle(families),
            )
        }
    }
}

/** Maps the design scale onto the Material roles so stock components pick up Inter and the scale. */
internal fun LagarTypography.toMaterial(): Typography = Typography(
    displayLarge = displayLg,
    displayMedium = displayLgMobile,
    displaySmall = displayLgMobile,
    headlineLarge = headlineLg,
    headlineMedium = headlineMd,
    headlineSmall = headlineSm,
    titleLarge = headlineSm,
    titleMedium = labelMd,
    titleSmall = labelMd,
    bodyLarge = bodyUi,
    bodyMedium = bodyUi,
    bodySmall = codeCitation,
    labelLarge = labelMd,
    labelMedium = labelSm,
    labelSmall = labelSm,
)
