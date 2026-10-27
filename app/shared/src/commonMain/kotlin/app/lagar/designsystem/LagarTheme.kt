package app.lagar.designsystem

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf

private val LocalDarkTheme = staticCompositionLocalOf { false }
private val LocalLayerColors = staticCompositionLocalOf { LayerColors(darkTheme = false) }
private val LocalLagarTypography = staticCompositionLocalOf<LagarTypography> {
    error("LagarTheme is not provided")
}
private val LocalLagarSpacing = staticCompositionLocalOf { LagarSpacing() }

@Composable
fun LagarTheme(darkTheme: Boolean, content: @Composable () -> Unit) {
    val colors = remember(darkTheme) { if (darkTheme) lagarDarkColorScheme() else lagarLightColorScheme() }
    val layers = remember(darkTheme) { LayerColors(darkTheme) }
    val type = rememberLagarTypography()
    CompositionLocalProvider(
        LocalDarkTheme provides darkTheme,
        LocalLayerColors provides layers,
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

object LagarTheme {
    val isDark: Boolean
        @Composable @ReadOnlyComposable get() = LocalDarkTheme.current

    val colors: ColorScheme
        @Composable @ReadOnlyComposable get() = MaterialTheme.colorScheme

    val layers: LayerColors
        @Composable @ReadOnlyComposable get() = LocalLayerColors.current

    val type: LagarTypography
        @Composable @ReadOnlyComposable get() = LocalLagarTypography.current

    val spacing: LagarSpacing
        @Composable @ReadOnlyComposable get() = LocalLagarSpacing.current
}
