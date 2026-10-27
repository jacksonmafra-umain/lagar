package app.lagar.designsystem

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.generated.LayerTokens

/**
 * Layer colors resolved for the current theme.
 *
 * - [accent]: icons, borders, indicator lines, chart series (never text).
 * - [onTint]: text and badge labels on a [tint] of the same layer.
 * - [tint]: the layer accent at 12% alpha in light and 16% in dark.
 */
@Immutable
class LayerColors(private val darkTheme: Boolean) {
    fun accent(k: LayerKey): Color = if (darkTheme) LayerTokens.dark(k) else LayerTokens.base(k)

    fun onTint(k: LayerKey): Color = if (darkTheme) LayerTokens.dark(k) else LayerTokens.text(k)

    fun tint(k: LayerKey): Color = accent(k).copy(alpha = if (darkTheme) TINT_ALPHA_DARK else TINT_ALPHA_LIGHT)

    /** Badge border: the layer accent at 20% alpha. */
    fun border(k: LayerKey): Color = accent(k).copy(alpha = BORDER_ALPHA)

    private companion object {
        const val TINT_ALPHA_LIGHT = 0.12f
        const val TINT_ALPHA_DARK = 0.16f
        const val BORDER_ALPHA = 0.20f
    }
}
