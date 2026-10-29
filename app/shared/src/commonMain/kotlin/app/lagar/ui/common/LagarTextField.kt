package app.lagar.ui.common

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawOutline
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.error
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.painterResource

/**
 * The DESIGN.md input frame shared by text fields and search command bars: `RadiusTokens.default` corners, a tier 1
 * glass fill (opaque under reduce transparency) and a 1dp [idleBorder]. A frame inside a glass bar, such as the search
 * screen's, gets its backdrop blur from the bar. While [focused] it draws a 1.5dp `primary` border and an outer
 * glow of `primary` at 15%; with [isError] the border is `error`. The row is at least 48dp tall.
 */
@Composable
internal fun InputFrame(
    focused: Boolean,
    modifier: Modifier = Modifier,
    isError: Boolean = false,
    idleBorder: Color = LagarTheme.colors.outlineVariant,
    contentPadding: PaddingValues = PaddingValues(horizontal = LagarTheme.spacing.md),
    content: @Composable RowScope.() -> Unit,
) {
    val colors = LagarTheme.colors
    val shape = MaterialTheme.shapes.small
    val active = if (isError) colors.error else colors.primary
    val border = if (focused || isError) BorderStroke(FocusBorderWidth, active) else BorderStroke(ShellDimens.Hairline, idleBorder)
    val glow = active.copy(alpha = FOCUS_GLOW_ALPHA)
    Row(
        modifier = modifier
            .then(if (focused) Modifier.focusGlow(glow) else Modifier)
            .glass(GlassTier.Card, shape = shape, border = border)
            .heightIn(min = ShellDimens.TouchTarget)
            .padding(contentPadding),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        content = content,
    )
}

/** A ring of [color] [GlowSpread] wide around the frame, following its corners. */
private fun Modifier.focusGlow(color: Color) = drawBehind {
    val spread = GlowSpread.toPx()
    val outline = GlowShape.createOutline(Size(size.width + 2 * spread, size.height + 2 * spread), layoutDirection, this)
    translate(-spread, -spread) { drawOutline(outline, color) }
}

/**
 * Text input in the DESIGN.md [InputFrame]: [label] above the field, [placeholder] inside it while empty,
 * an optional [leadingIcon], and [error] below (also announced as the field's error state). Single-line unless
 * [singleLine] is false; [minLines] then sets the visible height.
 */
@Composable
internal fun LagarTextField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    label: String? = null,
    placeholder: String? = null,
    error: String? = null,
    leadingIcon: DrawableResource? = null,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    keyboardActions: KeyboardActions = KeyboardActions.Default,
    singleLine: Boolean = true,
    minLines: Int = 1,
) {
    val colors = LagarTheme.colors
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()
    val description = label ?: placeholder
    Column(modifier, verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
        if (label != null) {
            // The field itself carries the label for screen readers.
            Text(
                label,
                style = LagarTheme.type.labelMd,
                color = if (error != null) colors.error else colors.onSurfaceVariant,
                modifier = Modifier.clearAndSetSemantics {},
            )
        }
        val padding = if (singleLine) {
            PaddingValues(horizontal = LagarTheme.spacing.md)
        } else {
            PaddingValues(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm)
        }
        InputFrame(focused = focused, isError = error != null, contentPadding = padding) {
            if (leadingIcon != null) {
                Icon(painterResource(leadingIcon), contentDescription = null, tint = colors.onSurfaceVariant, modifier = Modifier.size(ShellDimens.SmallIconSize))
            }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f).semantics {
                    if (description != null) contentDescription = description
                    if (error != null) error(error)
                },
                singleLine = singleLine,
                minLines = if (singleLine) 1 else minLines,
                textStyle = LagarTheme.type.bodyUi.copy(color = colors.onSurface),
                cursorBrush = SolidColor(if (error != null) colors.error else colors.primary),
                keyboardOptions = keyboardOptions,
                keyboardActions = keyboardActions,
                interactionSource = interactionSource,
                decorationBox = { field ->
                    Box(contentAlignment = if (singleLine) Alignment.CenterStart else Alignment.TopStart) {
                        if (value.isEmpty() && placeholder != null) {
                            Text(placeholder, style = LagarTheme.type.bodyUi, color = colors.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        field()
                    }
                },
            )
        }
        if (error != null) {
            Text(
                error,
                style = LagarTheme.type.labelSm,
                color = colors.error,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
    }
}

/** The `⌘K` / `Ctrl+K` key cap shown at the end of a search command bar on the web. */
@Composable
internal fun ShortcutHint(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text,
        style = LagarTheme.type.labelSm,
        color = LagarTheme.colors.onSurfaceVariant,
        maxLines = 1,
        modifier = modifier
            .border(ShellDimens.Hairline, LagarTheme.colors.outlineVariant, RoundedCornerShape(RadiusTokens.sm))
            .padding(horizontal = LagarTheme.spacing.xs, vertical = ShellDimens.TextGap),
    )
}

private val FocusBorderWidth = 1.5.dp
private val GlowSpread = 4.dp
private val GlowShape = RoundedCornerShape(RadiusTokens.default + GlowSpread)
private const val FOCUS_GLOW_ALPHA = 0.15f
