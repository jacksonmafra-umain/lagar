package app.lagar.designsystem

import androidx.compose.runtime.Composable

// Android has no reduce-transparency setting, and high-contrast text or disabled animations do not reliably mean
// the user wants opaque surfaces, so only the in-app setting applies here.
@Composable
internal actual fun systemReduceTransparency(): Boolean = false
