package app.lagar.ui.shell

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Density
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.app_tagline
import app.lagar.resources.ic_dark_mode
import app.lagar.resources.ic_gavel
import app.lagar.resources.ic_light_mode
import app.lagar.resources.ic_person
import app.lagar.resources.ic_search
import app.lagar.resources.menu_open
import app.lagar.resources.scope_institutions
import app.lagar.resources.scope_institutions_soon
import app.lagar.resources.search_open
import app.lagar.resources.tab_explore
import app.lagar.resources.tab_hierarchy
import app.lagar.resources.tab_saved
import app.lagar.resources.tab_search_filter
import app.lagar.resources.tab_services
import app.lagar.resources.theme_switch_to_dark
import app.lagar.resources.theme_switch_to_light
import app.lagar.resources.wide_search_button
import app.lagar.ui.navigation.AdvancedSearch
import app.lagar.ui.navigation.Hierarki
import app.lagar.ui.navigation.Sparade
import app.lagar.ui.navigation.Tjanster
import app.lagar.ui.navigation.Utforska
import app.lagar.ui.onboarding.nameRes
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Top bar destinations on wide windows: the four tabs plus "Search & filter", which opens the advanced search. */
internal enum class WideNav(val route: Any, val label: StringResource) {
    Explore(Utforska, Res.string.tab_explore),
    Hierarchy(Hierarki, Res.string.tab_hierarchy),
    SearchFilter(AdvancedSearch, Res.string.tab_search_filter),
    Saved(Sparade, Res.string.tab_saved),
    Services(Tjanster, Res.string.tab_services),
}

/**
 * Desktop top bar: wordmark, scope switch, navigation, search, theme toggle and the drawer button. The scope
 * switch needs [ShellDimens.FullScopeSwitchWidth]; below it the home's scope row is the only switch. The search
 * button shows its label only when the switch is hidden and the bar is at least [ShellDimens.SearchLabelWidth].
 */
@Composable
internal fun WideTopBar(
    hazeState: HazeState,
    selected: WideNav?,
    scope: Scope,
    onSelect: (WideNav) -> Unit,
    onSelectScope: (Scope) -> Unit,
    onOpenSearch: () -> Unit,
    onToggleTheme: () -> Unit,
    onMenuClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    val spacing = LagarTheme.spacing
    val dark = LagarTheme.isDark
    val density = LocalDensity.current
    CompositionLocalProvider(
        LocalDensity provides Density(density.density, fontScale = minOf(density.fontScale, MAX_BAR_FONT_SCALE)),
    ) {
        BoxWithConstraints(
            modifier = modifier
                .fillMaxWidth()
                .glass(GlassTier.Bar, hazeState)
                .windowInsetsPadding(WindowInsets.statusBars),
            contentAlignment = Alignment.Center,
        ) {
            val showScopes = maxWidth >= ShellDimens.FullScopeSwitchWidth
            val searchLabel = !showScopes && maxWidth >= ShellDimens.SearchLabelWidth
            Row(
                modifier = Modifier
                    .widthIn(max = ShellDimens.MaxContentWidth + spacing.margin * 2)
                    .fillMaxWidth()
                    .heightIn(min = ShellDimens.TopBarMinHeight)
                    .padding(horizontal = spacing.margin),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(spacing.md),
            ) {
                Wordmark(onClick = { onSelect(WideNav.Explore) })
                if (showScopes) ScopeSwitch(scope, onSelectScope)
                Row(
                    modifier = Modifier.weight(1f),
                    horizontalArrangement = Arrangement.spacedBy(spacing.xs, Alignment.CenterHorizontally),
                ) {
                    WideNav.entries.forEach { NavItem(it, it == selected) { onSelect(it) } }
                }
                SearchButton(compact = !searchLabel, onClick = onOpenSearch)
                BarButton(
                    onClick = onToggleTheme,
                    description = stringResource(if (dark) Res.string.theme_switch_to_light else Res.string.theme_switch_to_dark),
                ) {
                    Icon(
                        painterResource(if (dark) Res.drawable.ic_light_mode else Res.drawable.ic_dark_mode),
                        contentDescription = null,
                        tint = colors.onSurfaceVariant,
                        modifier = Modifier.size(ShellDimens.IconSize),
                    )
                }
                BarButton(onClick = onMenuClick, description = stringResource(Res.string.menu_open)) {
                    Box(
                        modifier = Modifier.size(ShellDimens.AvatarSize).clip(CircleShape).background(colors.primary),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(painterResource(Res.drawable.ic_person), null, tint = colors.onPrimary, modifier = Modifier.size(ShellDimens.SmallIconSize))
                    }
                }
            }
        }
    }
}

private const val MAX_BAR_FONT_SCALE = 1.3f

@Composable
private fun Wordmark(onClick: () -> Unit) {
    val colors = LagarTheme.colors
    Row(
        modifier = Modifier
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(MaterialTheme.shapes.medium)
            .clickable(role = Role.Button, onClick = onClick),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Box(
            modifier = Modifier.size(ShellDimens.LogoSize).clip(MaterialTheme.shapes.medium).background(colors.primary),
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(Res.drawable.ic_gavel), null, tint = colors.onPrimary, modifier = Modifier.size(ShellDimens.IconSize))
        }
        Column {
            Text(stringResource(Res.string.app_name), style = LagarTheme.type.headlineSm, color = colors.primary, maxLines = 1)
            Text(stringResource(Res.string.app_tagline), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant, maxLines = 1)
        }
    }
}

/** The three scopes, plus "Institutional" shown disabled until the app has agency-level content. */
@Composable
private fun ScopeSwitch(active: Scope, onSelect: (Scope) -> Unit) {
    val layers = LagarTheme.layers
    Row(
        modifier = Modifier.clip(CircleShape).background(LagarTheme.colors.surfaceContainer).padding(ShellDimens.TextGap),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Scope.entries.forEach { scope ->
            val selected = scope == active
            Box(
                modifier = Modifier
                    .heightIn(min = ShellDimens.AvatarSize)
                    .clip(CircleShape)
                    .selectable(selected = selected, role = Role.RadioButton, onClick = { onSelect(scope) })
                    .then(if (selected) Modifier.background(layers.tint(scope.key)) else Modifier)
                    .padding(horizontal = LagarTheme.spacing.sm),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = stringResource(scope.nameRes()),
                    style = LagarTheme.type.labelMd,
                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                    color = if (selected) layers.onTint(scope.key) else LagarTheme.colors.onSurfaceVariant,
                    maxLines = 1,
                )
            }
        }
        val soon = stringResource(Res.string.scope_institutions_soon)
        Box(
            modifier = Modifier
                .heightIn(min = ShellDimens.AvatarSize)
                .semantics { contentDescription = soon }
                .alpha(DISABLED_ALPHA)
                .padding(horizontal = LagarTheme.spacing.sm),
            contentAlignment = Alignment.Center,
        ) {
            Text(stringResource(Res.string.scope_institutions), style = LagarTheme.type.labelMd, color = LagarTheme.colors.onSurfaceVariant, maxLines = 1)
        }
    }
}

internal const val DISABLED_ALPHA = 0.5f

@Composable
private fun NavItem(item: WideNav, selected: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    val dark = LagarTheme.isDark
    Box(
        modifier = Modifier
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(CircleShape)
            .selectable(selected = selected, role = Role.Tab, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = stringResource(item.label),
            style = LagarTheme.type.labelMd,
            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            color = when {
                !selected -> colors.onSurfaceVariant
                dark -> colors.onPrimaryContainer
                else -> colors.onPrimaryFixedVariant
            },
            maxLines = 1,
            modifier = Modifier
                .clip(CircleShape)
                .then(if (selected) Modifier.background(if (dark) colors.primaryContainer else colors.primaryFixed) else Modifier)
                .padding(horizontal = LagarTheme.spacing.sm + LagarTheme.spacing.xs, vertical = ShellDimens.PillPaddingVertical),
        )
    }
}

@Composable
private fun SearchButton(compact: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    if (compact) {
        BarButton(onClick = onClick, description = stringResource(Res.string.search_open)) {
            Icon(painterResource(Res.drawable.ic_search), null, tint = colors.onSurfaceVariant, modifier = Modifier.size(ShellDimens.IconSize))
        }
        return
    }
    Surface(
        onClick = onClick,
        shape = CircleShape,
        color = colors.surfaceContainerLowest,
        border = BorderStroke(ShellDimens.Hairline, colors.outlineVariant),
        modifier = Modifier.heightIn(min = ShellDimens.TouchTarget),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Icon(painterResource(Res.drawable.ic_search), null, tint = colors.onSurfaceVariant, modifier = Modifier.size(ShellDimens.SmallIconSize))
            Text(
                stringResource(Res.string.wide_search_button),
                style = LagarTheme.type.labelMd,
                color = colors.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun BarButton(onClick: () -> Unit, description: String, content: @Composable () -> Unit) {
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) { content() }
}
