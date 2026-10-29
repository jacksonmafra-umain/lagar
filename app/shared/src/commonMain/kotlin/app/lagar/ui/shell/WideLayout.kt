package app.lagar.ui.shell

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import app.lagar.designsystem.LagarTheme

/**
 * True when the window is at least [ShellDimens.WideBreakpoint] wide: the shell then shows the top bar navigation
 * instead of the bottom bar, and screens may switch to their multi-column layout. Set by [AppShell].
 */
internal val LocalWideLayout = compositionLocalOf { false }

/** Caps the width at [ShellDimens.MaxContentWidth], centered, so single-column screens do not stretch on desktop. */
internal fun Modifier.maxContentWidth(): Modifier =
    wrapContentWidth(Alignment.CenterHorizontally).widthIn(max = ShellDimens.MaxContentWidth)

/** Centers [content] in a column capped at [ShellDimens.MaxContentWidth], with the desktop side margins. */
@Composable
internal fun WideContent(
    modifier: Modifier = Modifier,
    spacing: Dp = LagarTheme.spacing.md,
    content: @Composable ColumnScope.() -> Unit,
) {
    Box(modifier.fillMaxWidth(), contentAlignment = Alignment.TopCenter) {
        Column(
            modifier = Modifier
                .widthIn(max = ShellDimens.MaxContentWidth)
                .fillMaxWidth()
                .padding(horizontal = LagarTheme.spacing.margin),
            verticalArrangement = Arrangement.spacedBy(spacing),
            content = content,
        )
    }
}
