package app.lagar.ui.shell

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.intl.Locale
import androidx.compose.ui.text.toUpperCase
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.coming_soon
import app.lagar.resources.document_count
import app.lagar.resources.drawer_about
import app.lagar.resources.drawer_credits
import app.lagar.resources.drawer_data_built
import app.lagar.resources.drawer_section_navigate
import app.lagar.resources.drawer_section_scope
import app.lagar.resources.drawer_settings
import app.lagar.resources.home_advanced_search
import app.lagar.resources.home_choose_location
import app.lagar.resources.ic_info
import app.lagar.resources.ic_layer_crown
import app.lagar.resources.ic_search
import app.lagar.resources.ic_settings
import app.lagar.resources.scope_active
import app.lagar.resources.scope_national_short
import app.lagar.resources.splash_tagline
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.rememberDataBuildDate
import app.lagar.ui.onboarding.iconRes
import app.lagar.ui.onboarding.nameRes
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource
import app.lagar.ui.navigation.AdvancedSearch as AdvancedSearchDestination
import app.lagar.ui.navigation.Settings as SettingsDestination

/** The entries of the drawer below the scope card, in display order. */
internal enum class DrawerEntry(val route: Any, val label: StringResource, val icon: DrawableResource) {
    Explore(Tab.Explore.route, Tab.Explore.label, Tab.Explore.icon),
    Hierarchy(Tab.Hierarchy.route, Tab.Hierarchy.label, Tab.Hierarchy.icon),
    Saved(Tab.Saved.route, Tab.Saved.label, Tab.Saved.icon),
    Services(Tab.Services.route, Tab.Services.label, Tab.Services.icon),
    AdvancedSearch(AdvancedSearchDestination, Res.string.home_advanced_search, Res.drawable.ic_search),
    Settings(SettingsDestination, Res.string.drawer_settings, Res.drawable.ic_settings),
}

/**
 * Side drawer: app header; "Switch scope" with one row per scope ([onSelectScope] decides whether a tap
 * switches or opens the scope sheet); "Navigate" with the entries, Saved carrying [savedCount]; and, at the
 * bottom, the About block with the data build date. [localityNames] holds each scope's stored locality,
 * [scopeCounts] the document count per scope (null while loading or when the index failed). [selected] is the
 * entry matching the current route, if any.
 */
@Composable
internal fun LagarDrawerContent(
    hazeState: HazeState,
    activeScope: Scope,
    localityNames: Map<Scope, String?>,
    scopeCounts: Map<Scope, Int>?,
    savedCount: Int,
    selected: DrawerEntry?,
    onSelectScope: (Scope) -> Unit,
    onNavigate: (DrawerEntry) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    val builtAt by rememberDataBuildDate()
    BoxWithConstraints(
        modifier = modifier
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .padding(LagarTheme.spacing.xs)
            .width(ShellDimens.DrawerWidth)
            .fillMaxHeight()
            .glass(GlassTier.Overlay, hazeState)
            .padding(LagarTheme.spacing.md),
    ) {
        // Scrolls when the content outgrows the drawer (200% font, landscape); otherwise About sits at the bottom.
        Column(
            modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).heightIn(min = maxHeight),
            verticalArrangement = Arrangement.SpaceBetween,
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md)) {
                DrawerHeader()
                Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
                    SectionHeading(stringResource(Res.string.drawer_section_scope))
                    Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
                        Scope.entries.forEach { scope ->
                            ScopeRow(
                                scope = scope,
                                active = scope == activeScope,
                                localityName = localityNames[scope],
                                count = scopeCounts?.get(scope),
                                onClick = { onSelectScope(scope) },
                            )
                        }
                    }
                }
                Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
                    SectionHeading(stringResource(Res.string.drawer_section_navigate))
                    DrawerEntry.entries.forEach { entry ->
                        DrawerItem(
                            entry = entry,
                            selected = entry == selected,
                            badge = if (entry == DrawerEntry.Saved) savedBadgeCount(savedCount) else null,
                            onClick = { onNavigate(entry) },
                        )
                    }
                }
            }
            Spacer(Modifier.height(LagarTheme.spacing.md))
            Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
                SectionHeading(stringResource(Res.string.drawer_about))
                Row(verticalAlignment = Alignment.Top) {
                    Icon(
                        painter = painterResource(Res.drawable.ic_info),
                        contentDescription = null,
                        tint = colors.onSurfaceVariant,
                        modifier = Modifier.size(ShellDimens.SmallIconSize),
                    )
                    Column(Modifier.padding(start = LagarTheme.spacing.sm)) {
                        Text(stringResource(Res.string.drawer_credits), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
                        builtAt?.let {
                            Text(
                                text = stringResource(Res.string.drawer_data_built, it),
                                style = LagarTheme.type.labelSm,
                                color = colors.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
    }
}

/** Small upper-case section title, announced as a heading. */
@Composable
private fun SectionHeading(text: String) {
    Text(
        text = text.toUpperCase(Locale.current),
        style = LagarTheme.type.labelSm,
        fontWeight = FontWeight.Bold,
        color = LagarTheme.colors.onSurfaceVariant,
        modifier = Modifier.padding(horizontal = LagarTheme.spacing.xs).semantics { heading() },
    )
}

@Composable
private fun DrawerHeader() {
    val colors = LagarTheme.colors
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        Box(
            modifier = Modifier.size(ShellDimens.DrawerLogoSize).clip(CircleShape).background(colors.primary),
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(Res.drawable.ic_layer_crown), contentDescription = null, tint = colors.onPrimary, modifier = Modifier.size(ShellDimens.IconSize))
        }
        Column(Modifier.weight(1f)) {
            Text(stringResource(Res.string.app_name), style = LagarTheme.type.headlineMd, color = colors.primary)
            Text(stringResource(Res.string.splash_tagline), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
        }
    }
}

/**
 * One scope as a radio row: layer-tinted icon square, name, the stored locality (or a hint), and an
 * "Active" or document-count badge. The active row has a 2dp accent border.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ScopeRow(scope: Scope, active: Boolean, localityName: String?, count: Int?, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    val shape = MaterialTheme.shapes.large
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = ShellDimens.TouchTarget)
            .glass(
                GlassTier.Card,
                shape = shape,
                border = if (active) {
                    BorderStroke(ShellDimens.ActiveBorder, layers.accent(scope.key))
                } else {
                    BorderStroke(ShellDimens.Hairline, layers.border(scope.key))
                },
            )
            .clip(shape)
            .selectable(selected = active, role = Role.RadioButton, onClick = onClick)
            .padding(LagarTheme.spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Box(
            modifier = Modifier.size(ShellDimens.DrawerLogoSize).clip(MaterialTheme.shapes.medium).background(layers.tint(scope.key)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(scope.iconRes()), contentDescription = null, tint = layers.accent(scope.key), modifier = Modifier.size(ShellDimens.IconSize))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(ShellDimens.TextGap)) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
                verticalArrangement = Arrangement.spacedBy(ShellDimens.TextGap),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(scope.nameRes()),
                    style = LagarTheme.type.bodyUi,
                    fontWeight = FontWeight.Bold,
                    color = LagarTheme.colors.onSurface,
                )
                when {
                    active -> LayerBadge(scope.key, stringResource(Res.string.scope_active))
                    count == null -> Unit
                    count > 0 -> LayerBadge(scope.key, pluralStringResource(Res.plurals.document_count, count, count))
                    else -> LayerBadge(scope.key, stringResource(Res.string.coming_soon))
                }
            }
            Text(
                text = localityName ?: stringResource(
                    if (scope == Scope.Nationell) Res.string.scope_national_short else Res.string.home_choose_location,
                ),
                style = LagarTheme.type.labelSm,
                color = LagarTheme.colors.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun DrawerItem(entry: DrawerEntry, selected: Boolean, badge: Int?, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    val tint = if (selected) {
        if (LagarTheme.isDark) colors.onPrimaryContainer else colors.onPrimaryFixedVariant
    } else {
        colors.onSurfaceVariant
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(RoundedCornerShape(RadiusTokens.lg))
            .selectable(selected = selected, role = Role.Button, onClick = onClick)
            .then(
                if (selected) Modifier.background(if (LagarTheme.isDark) colors.primaryContainer else colors.primaryFixed) else Modifier,
            )
            .padding(horizontal = LagarTheme.spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(painterResource(entry.icon), contentDescription = null, tint = tint, modifier = Modifier.size(ShellDimens.IconSize))
        Text(
            text = stringResource(entry.label),
            style = LagarTheme.type.bodyUi,
            fontWeight = if (selected) FontWeight.Bold else null,
            color = if (selected) tint else colors.onSurface,
            modifier = Modifier.weight(1f).padding(start = LagarTheme.spacing.sm),
        )
        if (badge != null) {
            val description = pluralStringResource(Res.plurals.document_count, badge, badge)
            Text(
                text = badge.toString(),
                style = LagarTheme.type.labelSm,
                fontWeight = FontWeight.Bold,
                color = if (LagarTheme.isDark) colors.onPrimaryContainer else colors.onPrimaryFixedVariant,
                modifier = Modifier
                    .padding(start = LagarTheme.spacing.sm)
                    .clip(CircleShape)
                    .background(if (LagarTheme.isDark) colors.primaryContainer else colors.primaryFixed)
                    .padding(horizontal = LagarTheme.spacing.sm, vertical = ShellDimens.TextGap)
                    .semantics { contentDescription = description },
            )
        }
    }
}
