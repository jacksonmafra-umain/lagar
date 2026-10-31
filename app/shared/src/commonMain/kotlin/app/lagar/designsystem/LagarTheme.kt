package app.lagar.designsystem

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf

private val LocalDarkTheme = staticCompositionLocalOf { false }
private val LocalReduceTransparency = staticCompositionLocalOf { false }
private val LocalLayerColors = staticCompositionLocalOf { LayerColors(darkTheme = false) }
private val LocalLagarTypography = staticCompositionLocalOf<LagarTypography> {
    error("LagarTheme is not provided")
}
private val LocalStatusColors = staticCompositionLocalOf { StatusColors(darkTheme = false) }
private val LocalLagarSpacing = staticCompositionLocalOf { LagarSpacing() }

/** [reduceTransparency] makes every glass tier draw its opaque fallback (see [glass]). */
@Composable
fun LagarTheme(darkTheme: Boolean, reduceTransparency: Boolean = false, content: @Composable () -> Unit) {
    val colors = remember(darkTheme) { if (darkTheme) lagarDarkColorScheme() else lagarLightColorScheme() }
    val layers = remember(darkTheme) { LayerColors(darkTheme) }
    val status = remember(darkTheme) { StatusColors(darkTheme) }
    val type = rememberLagarTypography()
    CompositionLocalProvider(
        LocalDarkTheme provides darkTheme,
        LocalReduceTransparency provides reduceTransparency,
        LocalLayerColors provides layers,
        LocalStatusColors provides status,
        LocalLagarTypography provides type,
        LocalLagarSpacing provides LagarSpacing(),
    ) {
        MaterialTheme(
            colorScheme = colors,
            typography = remember(type) { type.toMaterial() },
            shapes = lagarShapes(),
            content = content,
        )
    }
}

/**
 * Re-themes one subtree with its own [colors] and [type] inside [LagarTheme]; the reader uses it for the paper and the
 * text settings of the person reading. [darkTheme] says whether [colors] is a dark scheme, for the layer and status
 * colors that sit on it.
 */
@Composable
fun LagarSubtheme(colors: ColorScheme, type: LagarTypography, darkTheme: Boolean, content: @Composable () -> Unit) {
    val layers = remember(darkTheme) { LayerColors(darkTheme) }
    val status = remember(darkTheme) { StatusColors(darkTheme) }
    CompositionLocalProvider(
        LocalDarkTheme provides darkTheme,
        LocalLayerColors provides layers,
        LocalStatusColors provides status,
        LocalLagarTypography provides type,
    ) {
        MaterialTheme(
            colorScheme = colors,
            typography = remember(type) { type.toMaterial() },
            shapes = MaterialTheme.shapes,
            content = content,
        )
    }
}

object LagarTheme {
    val isDark: Boolean
        @Composable @ReadOnlyComposable
        get() = LocalDarkTheme.current

    /** True when glass surfaces must be opaque: the user's setting or the platform's reduce transparency. */
    val reduceTransparency: Boolean
        @Composable @ReadOnlyComposable
        get() = LocalReduceTransparency.current

    val colors: ColorScheme
        @Composable @ReadOnlyComposable
        get() = MaterialTheme.colorScheme

    val layers: LayerColors
        @Composable @ReadOnlyComposable
        get() = LocalLayerColors.current

    val status: StatusColors
        @Composable @ReadOnlyComposable
        get() = LocalStatusColors.current

    val type: LagarTypography
        @Composable @ReadOnlyComposable
        get() = LocalLagarTypography.current

    val spacing: LagarSpacing
        @Composable @ReadOnlyComposable
        get() = LocalLagarSpacing.current
}
