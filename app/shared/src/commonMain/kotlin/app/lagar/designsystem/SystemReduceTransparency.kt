package app.lagar.designsystem

import androidx.compose.runtime.Composable

/**
 * Whether the platform's accessibility settings ask for less transparency, updated while the app runs: iOS
 * "Reduce Transparency", the web `prefers-reduced-transparency` media query. False where there is no such setting.
 */
@Composable
internal expect fun systemReduceTransparency(): Boolean
