package app.lagar.ui.common

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.ic_arrow_back
import app.lagar.resources.navigate_back
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/**
 * Height of a [BackTopBar] as measured, for padding the content below it. Seeded with the status bar
 * inset plus [ShellDimens.TopBarMinHeight] so the first frame is already close to the final layout.
 */
@Composable
internal fun rememberBackTopBarHeight(): MutableState<Dp> {
    val seed = WindowInsets.statusBars.asPaddingValues().calculateTopPadding() + ShellDimens.TopBarMinHeight
    return remember { mutableStateOf(seed) }
}

/** Glass top bar of the pushed screens: a back button followed by the caller's [title] content. */
@Composable
internal fun BackTopBar(
    hazeState: HazeState,
    onBack: () -> Unit,
    onHeightChange: (Dp) -> Unit,
    modifier: Modifier = Modifier,
    title: @Composable RowScope.() -> Unit,
) {
    val density = LocalDensity.current
    val colors = LagarTheme.colors
    Row(
        modifier = modifier
            .onSizeChanged { with(density) { onHeightChange(it.height.toDp()) } }
            .fillMaxWidth()
            .glass(GlassTier.Bar, hazeState)
            .windowInsetsPadding(WindowInsets.statusBars)
            .heightIn(min = ShellDimens.TopBarMinHeight)
            .padding(horizontal = LagarTheme.spacing.gutterMobile),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        val backDescription = stringResource(Res.string.navigate_back)
        Box(
            modifier = Modifier
                .size(ShellDimens.TouchTarget)
                .clip(CircleShape)
                .clickable(role = Role.Button, onClick = onBack)
                .semantics { contentDescription = backDescription },
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(Res.drawable.ic_arrow_back), contentDescription = null, tint = colors.onSurfaceVariant)
        }
        title()
    }
}
