package app.lagar.ui.shell

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import app.lagar.data.LagarRepository
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.drawer_about
import app.lagar.resources.drawer_credits
import app.lagar.resources.drawer_data_built
import app.lagar.resources.drawer_settings
import app.lagar.resources.ic_info
import app.lagar.resources.ic_settings
import dev.chrisbanes.haze.HazeState
import kotlin.coroutines.cancellation.CancellationException
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

@Composable
internal fun LagarDrawerContent(
    hazeState: HazeState,
    onSettingsClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    val repository = koinInject<LagarRepository>()
    // ISO date of the data build; omitted when the index cannot be loaded.
    val builtAt by produceState<String?>(initialValue = null, repository) {
        value = try {
            repository.index().builtAt.take(10)
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
    }
    Column(
        modifier = modifier
            .windowInsetsPadding(WindowInsets.safeDrawing)
            .padding(LagarTheme.spacing.xs)
            .width(ShellDimens.DrawerWidth)
            .fillMaxHeight()
            .glass(GlassTier.Overlay, hazeState)
            .padding(LagarTheme.spacing.md),
    ) {
        Text(
            text = stringResource(Res.string.app_name),
            style = LagarTheme.type.headlineMd,
            color = colors.primary,
        )
        Spacer(Modifier.height(LagarTheme.spacing.md))
        DrawerItem(painterResource(Res.drawable.ic_settings), stringResource(Res.string.drawer_settings), onSettingsClick)
        Spacer(Modifier.weight(1f))
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

@Composable
private fun DrawerItem(icon: androidx.compose.ui.graphics.painter.Painter, label: String, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = ShellDimens.TouchTarget)
            .clickable(role = Role.Button, onClick = onClick),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, tint = colors.onSurfaceVariant, modifier = Modifier.size(ShellDimens.IconSize))
        Text(
            text = label,
            style = LagarTheme.type.bodyUi,
            color = colors.onSurface,
            modifier = Modifier.padding(start = LagarTheme.spacing.sm),
        )
    }
}
