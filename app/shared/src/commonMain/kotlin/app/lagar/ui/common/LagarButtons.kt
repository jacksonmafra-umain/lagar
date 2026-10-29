package app.lagar.ui.common

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import app.lagar.designsystem.LagarTheme
import app.lagar.ui.shell.ShellDimens

/**
 * DESIGN.md primary button: solid fill, `RadiusTokens.default` corners, a subtle 1dp highlight edge and a 48dp minimum
 * height. The fill is `primary` by default; pass a layer `accent` with its `iconColor()` for a layer-coloured action.
 */
@Composable
internal fun LagarButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    containerColor: Color = LagarTheme.colors.primary,
    contentColor: Color = LagarTheme.colors.onPrimary,
    content: @Composable RowScope.() -> Unit,
) {
    Button(
        onClick = onClick,
        modifier = modifier.heightIn(min = ShellDimens.TouchTarget),
        enabled = enabled,
        shape = MaterialTheme.shapes.small,
        colors = ButtonDefaults.buttonColors(containerColor = containerColor, contentColor = contentColor),
        border = if (enabled) BorderStroke(ShellDimens.Hairline, contentColor.copy(alpha = HIGHLIGHT_ALPHA)) else null,
        content = content,
    )
}

/**
 * DESIGN.md glass secondary button: translucent `surfaceContainerLowest` fill (opaque under reduce transparency), 1dp `outlineVariant` edge, text in
 * [contentColor] (`primary` by default, or a layer `onTint`), `RadiusTokens.default` corners and a 48dp minimum height.
 */
@Composable
internal fun LagarSecondaryButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentColor: Color = LagarTheme.colors.primary,
    content: @Composable RowScope.() -> Unit,
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.heightIn(min = ShellDimens.TouchTarget),
        enabled = enabled,
        shape = MaterialTheme.shapes.small,
        colors = ButtonDefaults.outlinedButtonColors(
            // Reduce transparency makes the glass fill opaque, like the glass tiers.
            containerColor = LagarTheme.colors.surfaceContainerLowest.let {
                if (LagarTheme.reduceTransparency) it else it.copy(alpha = SECONDARY_FILL_ALPHA)
            },
            contentColor = contentColor,
        ),
        border = BorderStroke(ShellDimens.Hairline, LagarTheme.colors.outlineVariant),
        content = content,
    )
}

private const val HIGHLIGHT_ALPHA = 0.16f
private const val SECONDARY_FILL_ALPHA = 0.6f
