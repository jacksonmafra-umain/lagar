package app.lagar.ui.common

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Shape
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass

/** The top-rounded `RadiusTokens.xl` shape of the modal sheets. */
internal val SheetShape: Shape = RoundedCornerShape(topStart = RadiusTokens.xl, topEnd = RadiusTokens.xl)

/**
 * The tier 3 glass of a modal bottom sheet, set on the sheet itself so the drag handle sits on it too; pass a
 * transparent `containerColor`. A modal sheet is drawn in its own window (a dialog on Android, a popup layer elsewhere),
 * and Haze can only blur content of the window it draws in, so there is no backdrop to sample: the tier always draws
 * its opaque `surfaceContainerHigh` fallback, with the frosted border, highlight and shadow.
 */
@Composable
internal fun Modifier.sheetGlass(shape: Shape = SheetShape): Modifier = glass(GlassTier.Overlay, hazeState = null, shape = shape)
