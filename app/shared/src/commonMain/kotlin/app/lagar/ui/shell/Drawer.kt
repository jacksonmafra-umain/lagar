package app.lagar.ui.shell

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.RadiusTokens
import app.lagar.designsystem.glass
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.drawer_about
import app.lagar.resources.drawer_change
import app.lagar.resources.drawer_credits
import app.lagar.resources.drawer_data_built
import app.lagar.resources.drawer_settings
import app.lagar.resources.home_advanced_search
import app.lagar.resources.home_choose_location
import app.lagar.resources.ic_info
import app.lagar.resources.ic_layer_crown
import app.lagar.resources.ic_search
import app.lagar.resources.ic_settings
import app.lagar.resources.scope_national_desc
import app.lagar.resources.splash_tagline
import app.lagar.ui.common.rememberDataBuildDate
import app.lagar.ui.onboarding.nameRes
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
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
 * Side drawer: app header, the active scope with its locality (opens the scope sheet), navigation
 * entries and, at the bottom, the About block with the data build date. [selected] is the entry
 * matching the current route, if any.
 */
@Composable
internal fun LagarDrawerContent(
    hazeState: HazeState,
    scope: Scope,
    localityName: String?,
    selected: DrawerEntry?,
    onChangeScope: () -> Unit,
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
                ScopeCard(scope, localityName, onChangeScope)
                Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
                    DrawerEntry.entries.forEach { entry ->
                        DrawerItem(entry, selected = entry == selected, onClick = { onNavigate(entry) })
                    }
                }
            }
            Spacer(Modifier.height(LagarTheme.spacing.md))
            Row(verticalAlignment = Alignment.Top) {
                Icon(
                    painter = painterResource(Res.drawable.ic_info),
                    contentDescription = null,
                    tint = colors.onSurfaceVariant,
                    modifier = Modifier.size(ShellDimens.SmallIconSize),
                )
                Column(Modifier.padding(start = LagarTheme.spacing.sm)) {
                    Text(stringResource(Res.string.drawer_about), style = LagarTheme.type.labelMd, color = colors.onSurface)
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

/** Active scope and its locality in the scope's colors; the whole card and the "Change" pill open the scope sheet. */
@Composable
private fun ScopeCard(scope: Scope, localityName: String?, onChange: () -> Unit) {
    val layers = LagarTheme.layers
    Surface(
        onClick = onChange,
        modifier = Modifier.fillMaxWidth()
            .glass(GlassTier.Card, shape = MaterialTheme.shapes.large, border = BorderStroke(ShellDimens.Hairline, layers.border(scope.key))),
        shape = MaterialTheme.shapes.large,
        color = Color.Transparent,
    ) {
        // The text block and the pill share a row until a large font leaves the text too narrow; then the pill drops below.
        val stacked = LocalDensity.current.fontScale > WRAP_FONT_SCALE
        val texts: @Composable (Modifier) -> Unit = { textModifier ->
            Column(textModifier, verticalArrangement = Arrangement.spacedBy(ShellDimens.TextGap)) {
                Text(
                    text = stringResource(scope.nameRes()),
                    style = LagarTheme.type.bodyUi,
                    fontWeight = FontWeight.Bold,
                    color = LagarTheme.colors.onSurface,
                )
                Text(
                    text = localityName ?: stringResource(
                        if (scope == Scope.Nationell) Res.string.scope_national_desc else Res.string.home_choose_location,
                    ),
                    style = LagarTheme.type.labelSm,
                    color = LagarTheme.colors.onSurfaceVariant,
                )
            }
        }
        val pill: @Composable () -> Unit = {
            Text(
                text = stringResource(Res.string.drawer_change),
                style = LagarTheme.type.labelMd,
                fontWeight = FontWeight.Bold,
                color = layers.onTint(scope.key),
                modifier = Modifier
                    .clip(CircleShape)
                    .background(layers.tint(scope.key))
                    .padding(horizontal = LagarTheme.spacing.sm, vertical = ShellDimens.PillPaddingVertical),
            )
        }
        if (stacked) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(LagarTheme.spacing.sm),
                horizontalAlignment = Alignment.Start,
                verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            ) {
                texts(Modifier)
                pill()
            }
        } else {
            Row(
                modifier = Modifier.padding(LagarTheme.spacing.sm),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            ) {
                texts(Modifier.weight(1f))
                pill()
            }
        }
    }
}

@Composable
private fun DrawerItem(entry: DrawerEntry, selected: Boolean, onClick: () -> Unit) {
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
            modifier = Modifier.padding(start = LagarTheme.spacing.sm),
        )
    }
}

// Above this font scale the scope card stacks its pill under the text.
private const val WRAP_FONT_SCALE = 1.3f
