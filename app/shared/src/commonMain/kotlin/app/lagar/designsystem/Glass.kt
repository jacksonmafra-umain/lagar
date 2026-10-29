package app.lagar.designsystem

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.ColorMatrix
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.generated.DarkTokens
import app.lagar.designsystem.generated.RadiusTokens
import dev.chrisbanes.haze.HazeInput
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.blur.HazeBlurStyle
import dev.chrisbanes.haze.blur.HazeColorEffect
import dev.chrisbanes.haze.blur.hazeBlur

/**
 * Liquid Glass elevation tiers from DESIGN.md.
 *
 * - [Card]: tier 1, article cards and document body. Translucent fill, no blur.
 * - [Bar]: tier 2, sticky headers and norm bars. Blur 20dp, ambient aura.
 * - [Overlay]: tier 3, floating overlays and drawers. Blur 28dp, diffuse shadow.
 */
enum class GlassTier { Card, Bar, Overlay }

private class GlassSpec(
    val fillAlpha: Float,
    val blur: Dp?,
    val shadow: Dp,
    val shadowLight: Color,
    val shadowDark: Color,
    val shape: Shape,
)

private fun GlassTier.spec(): GlassSpec = when (this) {
    GlassTier.Card -> GlassSpec(
        fillAlpha = 0.85f, blur = null, shadow = 0.dp,
        shadowLight = Color.Transparent, shadowDark = Color.Transparent,
        shape = RoundedCornerShape(RadiusTokens.lg),
    )
    GlassTier.Bar -> GlassSpec(
        fillAlpha = 0.72f, blur = 20.dp, shadow = 8.dp,
        shadowLight = Color(0xFF0B3D91).copy(alpha = 0.04f), shadowDark = Color.Black.copy(alpha = 0.24f),
        shape = RectangleShape,
    )
    GlassTier.Overlay -> GlassSpec(
        fillAlpha = 0.88f, blur = 28.dp, shadow = 16.dp,
        shadowLight = Color.Black.copy(alpha = 0.08f), shadowDark = Color.Black.copy(alpha = 0.4f),
        shape = RoundedCornerShape(RadiusTokens.xl),
    )
}

/** How a glass surface fills its shape. */
internal enum class GlassFill {
    /** Haze blurs the content behind and tints it with the translucent fill. */
    Blurred,

    /** The translucent fill alone; tier 1 has no blur. */
    Translucent,

    /** The opaque `surfaceContainer*` fallback. */
    Opaque,
}

/**
 * Picks the fill of a [tier] surface. Reduce transparency always gets the opaque fallback. Otherwise [GlassTier.Card]
 * is translucent without blur, and [GlassTier.Bar] and [GlassTier.Overlay] blur when [hasBlurSource] (a `HazeState`
 * with content behind) and fall back to opaque when there is nothing to blur.
 */
internal fun glassFill(tier: GlassTier, hasBlurSource: Boolean, reduceTransparency: Boolean): GlassFill = when {
    reduceTransparency -> GlassFill.Opaque
    tier == GlassTier.Card -> GlassFill.Translucent
    hasBlurSource -> GlassFill.Blurred
    else -> GlassFill.Opaque
}

/**
 * Draws a Liquid Glass surface for [tier]: translucent fill, frosted border and specular highlight, with a backdrop
 * blur (blur 20dp / 28dp, saturate 180%) behind [GlassTier.Bar] and [GlassTier.Overlay] when [hazeState] is given.
 * The glass samples content marked with `Modifier.hazeSource(hazeState)`. [GlassTier.Card] never blurs, so it
 * ignores [hazeState]. A non-null [border] replaces the frosted border, for cards with a layer or focus edge.
 *
 * With reduce transparency on ([LagarTheme.reduceTransparency]), with a null [hazeState] on a blurred tier, or on
 * targets where Haze cannot blur, the surface falls back to an opaque `surfaceContainer*` fill with the same border.
 */
@Composable
fun Modifier.glass(
    tier: GlassTier,
    hazeState: HazeState? = null,
    shape: Shape? = null,
    border: BorderStroke? = null,
): Modifier {
    val dark = LagarTheme.isDark
    val colors = LagarTheme.colors
    val spec = remember(tier) { tier.spec() }
    val outline = shape ?: spec.shape
    val fillKind = glassFill(tier, hasBlurSource = hazeState != null, reduceTransparency = LagarTheme.reduceTransparency)

    val opaque = when (tier) {
        GlassTier.Card -> if (dark) colors.surfaceContainerLow else colors.surfaceContainerLowest
        GlassTier.Bar -> colors.surfaceContainer
        GlassTier.Overlay -> colors.surfaceContainerHigh
    }
    // Light glass is translucent white; dark glass is the dark surface.
    val fill = (if (dark) DarkTokens.surface else Color.White).copy(alpha = spec.fillAlpha)
    val highlight = if (dark) Color.White.copy(alpha = 0.08f) else Color.White.copy(alpha = 0.4f)
    val frostedBorder = remember(dark) {
        val frosted = if (dark) Color.White.copy(alpha = 0.12f) else Color.White.copy(alpha = 0.65f)
        val outer = if (dark) Color.Black.copy(alpha = 0.4f) else Color.Black.copy(alpha = 0.06f)
        Brush.verticalGradient(listOf(frosted, outer))
    }

    var m = this
    if (spec.shadow > 0.dp) {
        val shadowColor = if (dark) spec.shadowDark else spec.shadowLight
        m = m.shadow(spec.shadow, outline, clip = false, ambientColor = shadowColor, spotColor = shadowColor)
    }
    m = m.clip(outline)

    m = when (fillKind) {
        GlassFill.Blurred -> {
            val blur = requireNotNull(spec.blur)
            val style = remember(blur, dark, fill, opaque) {
                HazeBlurStyle {
                    blurRadius(blur)
                    backgroundColor(opaque)
                    colorEffects(
                        listOf(
                            HazeColorEffect.colorFilter(ColorFilter.colorMatrix(ColorMatrix().apply { setToSaturation(1.8f) })),
                            HazeColorEffect.tint(fill),
                        ),
                    )
                    fallbackColorEffect(HazeColorEffect.tint(opaque))
                }
            }
            m.hazeBlur(HazeInput.Sources(requireNotNull(hazeState)), style)
        }
        GlassFill.Translucent -> m.background(fill)
        GlassFill.Opaque -> m.background(opaque)
    }

    m = m.drawBehind {
        val h = minOf(size.height, 48.dp.toPx())
        drawRect(
            brush = Brush.verticalGradient(listOf(highlight, Color.Transparent), startY = 0f, endY = h),
            size = Size(size.width, h),
        )
    }
    return if (border != null) m.border(border, outline) else m.border(1.dp, frostedBorder, outline)
}
