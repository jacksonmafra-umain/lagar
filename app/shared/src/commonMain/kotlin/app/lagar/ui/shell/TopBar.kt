package app.lagar.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import app.lagar.resources.home_scope_chip
import app.lagar.resources.ic_dark_mode
import app.lagar.resources.ic_expand_more
import app.lagar.resources.ic_light_mode
import app.lagar.resources.ic_person
import app.lagar.resources.ic_search
import app.lagar.resources.menu_open
import app.lagar.resources.search_open
import app.lagar.resources.theme_switch_to_dark
import app.lagar.resources.theme_switch_to_light
import app.lagar.ui.onboarding.nameRes
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

@Composable
internal fun LagarTopBar(
    hazeState: HazeState,
    onMenuClick: () -> Unit,
    onToggleTheme: () -> Unit,
    onOpenSearch: () -> Unit,
    scope: Scope,
    onOpenScopeSheet: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    val dark = LagarTheme.isDark
    // The bar holds the title, the scope chip and three icon buttons on one line, so like the bottom bar
    // it caps text scaling; the chip and buttons keep their full accessible names.
    val density = LocalDensity.current
    CompositionLocalProvider(
        LocalDensity provides Density(density.density, fontScale = minOf(density.fontScale, MAX_BAR_FONT_SCALE)),
    ) {
        Row(
            modifier = modifier
                .fillMaxWidth()
                .glass(GlassTier.Bar, hazeState)
                .windowInsetsPadding(WindowInsets.statusBars)
                .heightIn(min = ShellDimens.TopBarMinHeight)
                .padding(horizontal = LagarTheme.spacing.gutterMobile),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(Res.string.app_name),
                style = LagarTheme.type.headlineSm,
                color = colors.primary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            ScopeChip(scope, onOpenScopeSheet)
            BarIconButton(onClick = onOpenSearch, description = stringResource(Res.string.search_open)) {
                Icon(
                    painter = painterResource(Res.drawable.ic_search),
                    contentDescription = null,
                    tint = colors.onSurfaceVariant,
                    modifier = Modifier.size(ShellDimens.IconSize),
                )
            }
            BarIconButton(
                onClick = onToggleTheme,
                description = stringResource(
                    if (dark) Res.string.theme_switch_to_light else Res.string.theme_switch_to_dark,
                ),
            ) {
                Icon(
                    painter = painterResource(if (dark) Res.drawable.ic_light_mode else Res.drawable.ic_dark_mode),
                    contentDescription = null,
                    tint = colors.onSurfaceVariant,
                    modifier = Modifier.size(ShellDimens.IconSize),
                )
            }
            BarIconButton(onClick = onMenuClick, description = stringResource(Res.string.menu_open)) {
                Box(
                    modifier = Modifier.size(ShellDimens.AvatarSize).clip(CircleShape).background(colors.primary),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        painter = painterResource(Res.drawable.ic_person),
                        contentDescription = null,
                        tint = colors.onPrimary,
                        modifier = Modifier.size(ShellDimens.SmallIconSize),
                    )
                }
            }
        }
    }
}

private const val MAX_BAR_FONT_SCALE = 1.3f

@Composable
private fun BarIconButton(
    onClick: () -> Unit,
    description: String,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) { content() }
}

/** Current scope (short name and a drop-down arrow); opens the scope switch. */
@Composable
private fun ScopeChip(scope: Scope, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    val name = stringResource(scope.nameRes())
    val description = stringResource(Res.string.home_scope_chip, name)
    Row(
        modifier = Modifier
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description }
            .padding(horizontal = LagarTheme.spacing.xs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            modifier = Modifier
                .clip(CircleShape)
                .background(layers.tint(scope.key))
                .padding(start = LagarTheme.spacing.sm, end = LagarTheme.spacing.xs, top = ShellDimens.PillPaddingVertical, bottom = ShellDimens.PillPaddingVertical),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = name,
                style = LagarTheme.type.labelMd,
                fontWeight = FontWeight.Bold,
                color = layers.onTint(scope.key),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Icon(painterResource(Res.drawable.ic_expand_more), null, tint = layers.onTint(scope.key), modifier = Modifier.size(ShellDimens.SmallIconSize))
        }
    }
}
