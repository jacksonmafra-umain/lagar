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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.material3.Text
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.ic_dark_mode
import app.lagar.resources.ic_light_mode
import app.lagar.resources.ic_person
import app.lagar.resources.menu_open
import app.lagar.resources.theme_switch_to_dark
import app.lagar.resources.theme_switch_to_light
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

@Composable
internal fun LagarTopBar(
    hazeState: HazeState,
    onMenuClick: () -> Unit,
    onToggleTheme: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    val dark = LagarTheme.isDark
    Row(
        modifier = modifier
            .fillMaxWidth()
            .glass(GlassTier.Bar, hazeState)
            .windowInsetsPadding(WindowInsets.statusBars)
            .heightIn(min = 64.dp)
            .padding(horizontal = LagarTheme.spacing.gutterMobile),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = stringResource(Res.string.app_name),
            style = LagarTheme.type.headlineSm,
            color = colors.primary,
            modifier = Modifier.weight(1f),
        )
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
                modifier = Modifier.size(24.dp),
            )
        }
        BarIconButton(onClick = onMenuClick, description = stringResource(Res.string.menu_open)) {
            Box(
                modifier = Modifier.size(32.dp).clip(CircleShape).background(colors.primary),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    painter = painterResource(Res.drawable.ic_person),
                    contentDescription = null,
                    tint = colors.onPrimary,
                    modifier = Modifier.size(20.dp),
                )
            }
        }
    }
}

@Composable
private fun BarIconButton(
    onClick: () -> Unit,
    description: String,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) { content() }
}
