package app.lagar.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.ic_account_tree
import app.lagar.resources.ic_bookmarks
import app.lagar.resources.ic_gavel
import app.lagar.resources.ic_menu_book
import app.lagar.resources.tab_explore
import app.lagar.resources.tab_hierarchy
import app.lagar.resources.tab_saved
import app.lagar.resources.tab_services
import app.lagar.ui.navigation.Hierarki
import app.lagar.ui.navigation.Sparade
import app.lagar.ui.navigation.Tjanster
import app.lagar.ui.navigation.Utforska
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

internal enum class Tab(val route: Any, val label: StringResource, val icon: DrawableResource) {
    Explore(Utforska, Res.string.tab_explore, Res.drawable.ic_menu_book),
    Hierarchy(Hierarki, Res.string.tab_hierarchy, Res.drawable.ic_account_tree),
    Saved(Sparade, Res.string.tab_saved, Res.drawable.ic_bookmarks),
    Services(Tjanster, Res.string.tab_services, Res.drawable.ic_gavel),
}

@Composable
internal fun LagarBottomBar(
    selected: Tab?,
    hazeState: HazeState,
    onSelect: (Tab) -> Unit,
    modifier: Modifier = Modifier,
) {
    // Four equal-width tabs cannot hold a 200% label, so the bar caps text scaling at 1.3 (the icon
    // and selected pill still make each tab identifiable).
    val density = LocalDensity.current
    CompositionLocalProvider(
        LocalDensity provides Density(density.density, fontScale = minOf(density.fontScale, MAX_LABEL_FONT_SCALE)),
    ) {
        Row(
            modifier = modifier
                .fillMaxWidth()
                .glass(GlassTier.Bar, hazeState)
                .windowInsetsPadding(WindowInsets.navigationBars)
                .padding(horizontal = LagarTheme.spacing.xs, vertical = LagarTheme.spacing.xs),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Tab.entries.forEach { tab ->
                TabItem(tab, tab == selected, onClick = { onSelect(tab) }, modifier = Modifier.weight(1f))
            }
        }
    }
}

private const val MAX_LABEL_FONT_SCALE = 1.3f

@Composable
private fun TabItem(tab: Tab, selected: Boolean, onClick: () -> Unit, modifier: Modifier) {
    val colors = LagarTheme.colors
    val label = stringResource(tab.label)
    Column(
        modifier = modifier
            .heightIn(min = ShellDimens.TabMinHeight)
            .clip(RoundedCornerShape(RadiusTokens.lg))
            .selectable(selected = selected, role = Role.Tab, onClick = onClick)
            .then(if (selected) Modifier.background(if (LagarTheme.isDark) colors.primaryContainer else colors.primaryFixed) else Modifier)
            .padding(vertical = LagarTheme.spacing.xs),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        val tint = if (selected) (if (LagarTheme.isDark) colors.onPrimaryContainer else colors.onPrimaryFixedVariant) else colors.onSurfaceVariant
        Icon(painterResource(tab.icon), contentDescription = null, tint = tint, modifier = Modifier.size(ShellDimens.IconSize))
        Text(
            text = label,
            style = LagarTheme.type.labelSm,
            color = tint,
            maxLines = 1,
            overflow = TextOverflow.Clip,
            textAlign = TextAlign.Center,
        )
    }
}
