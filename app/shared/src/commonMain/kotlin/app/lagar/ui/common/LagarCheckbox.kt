package app.lagar.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.minimumInteractiveComponentSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.resources.Res
import app.lagar.resources.ic_check
import org.jetbrains.compose.resources.painterResource

/**
 * DESIGN.md checkbox: an 18dp square with `RadiusTokens.sm` (4dp) corners; checked, it fills with [color] (a layer
 * `accent` or `primary`) and shows a check in `iconColor()`. With a null [onCheckedChange] it is decoration only and
 * the caller's row carries the `toggleable` semantics; otherwise it is its own 48dp checkbox target.
 */
@Composable
internal fun LagarCheckbox(
    checked: Boolean,
    onCheckedChange: ((Boolean) -> Unit)?,
    modifier: Modifier = Modifier,
    color: Color = LagarTheme.colors.primary,
    enabled: Boolean = true,
) {
    val interactive = if (onCheckedChange != null) {
        Modifier
            .minimumInteractiveComponentSize()
            .toggleable(value = checked, enabled = enabled, role = Role.Checkbox, onValueChange = onCheckedChange)
    } else {
        Modifier
    }
    val shape = RoundedCornerShape(RadiusTokens.sm)
    Box(modifier.then(interactive), contentAlignment = Alignment.Center) {
        Box(
            modifier = Modifier
                .alpha(if (enabled) 1f else DISABLED_ALPHA)
                .size(BoxSize)
                .clip(shape)
                .then(
                    if (checked) {
                        Modifier.background(color)
                    } else {
                        Modifier.border(BorderWidth, LagarTheme.colors.onSurfaceVariant, shape)
                    },
                ),
            contentAlignment = Alignment.Center,
        ) {
            if (checked) {
                Icon(painterResource(Res.drawable.ic_check), contentDescription = null, tint = color.iconColor(), modifier = Modifier.size(CheckSize))
            }
        }
    }
}

private val BoxSize = 18.dp
private val CheckSize = 14.dp
private val BorderWidth = 2.dp
private const val DISABLED_ALPHA = 0.38f
