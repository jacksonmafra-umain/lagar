package app.lagar.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SheetState
import androidx.compose.material3.SheetValue
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.semantics.collapse
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.dismiss
import androidx.compose.ui.semantics.expand
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.sheet_collapse
import app.lagar.resources.sheet_dismiss
import app.lagar.resources.sheet_drag_handle
import app.lagar.resources.sheet_expand
import kotlinx.coroutines.launch
import org.jetbrains.compose.resources.stringResource

/** The top-rounded `RadiusTokens.xl` shape of the modal sheets. */
internal val SheetShape: Shape = RoundedCornerShape(topStart = RadiusTokens.xl, topEnd = RadiusTokens.xl)

/**
 * The tier 3 glass of a modal bottom sheet. A modal sheet is drawn in its own window (a dialog on Android, a popup
 * layer elsewhere), and Haze can only blur content of the window it draws in, so there is no backdrop to sample: the
 * tier always draws its opaque `surfaceContainerHigh` fallback, with the frosted border, highlight and shadow.
 */
@Composable
internal fun Modifier.sheetGlass(shape: Shape = SheetShape): Modifier = glass(GlassTier.Overlay, hazeState = null, shape = shape)

/**
 * A modal bottom sheet on tier 3 glass, with the screen behind it dimmed by the scrim. The glass is drawn by the
 * sheet's content, which moves with the sheet: a modifier on [ModalBottomSheet] itself is laid out before the sheet
 * is offset, so it would cover the top of the screen instead of the sheet. The drag handle is drawn here too, on the
 * glass, with the expand, collapse and dismiss actions of the stock one.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun GlassBottomSheet(
    onDismissRequest: () -> Unit,
    sheetState: SheetState = rememberModalBottomSheetState(),
    shape: Shape = SheetShape,
    content: @Composable ColumnScope.() -> Unit,
) {
    val scope = rememberCoroutineScope()
    val dismiss: () -> Unit = {
        scope.launch { sheetState.hide() }.invokeOnCompletion { if (!sheetState.isVisible) onDismissRequest() }
    }
    ModalBottomSheet(
        onDismissRequest = onDismissRequest,
        sheetState = sheetState,
        shape = shape,
        containerColor = Color.Transparent,
        contentColor = LagarTheme.colors.onSurface,
        tonalElevation = 0.dp,
        dragHandle = null,
    ) {
        Column(Modifier.fillMaxWidth().sheetGlass(shape)) {
            SheetHandle(sheetState, onDismiss = dismiss, modifier = Modifier.align(Alignment.CenterHorizontally))
            content()
        }
    }
}

/** The 32x4dp handle in `onSurfaceVariant`; a tap expands a half-open sheet and dismisses an open one. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SheetHandle(state: SheetState, onDismiss: () -> Unit, modifier: Modifier = Modifier) {
    val scope = rememberCoroutineScope()
    val description = stringResource(Res.string.sheet_drag_handle)
    val expandLabel = stringResource(Res.string.sheet_expand)
    val collapseLabel = stringResource(Res.string.sheet_collapse)
    val dismissLabel = stringResource(Res.string.sheet_dismiss)
    Box(
        modifier = modifier
            .clickable {
                if (state.currentValue == SheetValue.PartiallyExpanded) scope.launch { state.expand() } else onDismiss()
            }
            .semantics(mergeDescendants = true) {
                contentDescription = description
                dismiss(dismissLabel) {
                    onDismiss()
                    true
                }
                if (state.currentValue == SheetValue.PartiallyExpanded) {
                    expand(expandLabel) {
                        scope.launch { state.expand() }
                        true
                    }
                } else if (state.hasPartiallyExpandedState) {
                    collapse(collapseLabel) {
                        scope.launch { state.partialExpand() }
                        true
                    }
                }
            }
            .padding(horizontal = LagarTheme.spacing.md, vertical = HandlePadding),
    ) {
        Box(Modifier.size(width = 32.dp, height = 4.dp).background(LagarTheme.colors.onSurfaceVariant, CircleShape))
    }
}

// Space above and below the handle, as in the Material sheet; with the 4dp bar it makes a 48dp touch target.
private val HandlePadding = 22.dp
