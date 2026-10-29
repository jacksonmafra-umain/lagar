package app.lagar.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.error_retry
import app.lagar.resources.home_partial_error
import app.lagar.resources.ic_info
import app.lagar.ui.common.LagarSecondaryButton
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Says that part of the home could not be loaded, above what did load, with a retry. */
@Composable
internal fun PartialLoadNotice(onRetry: () -> Unit, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        color = LagarTheme.colors.surfaceContainerHigh,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = spacing.md, vertical = spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            Icon(painterResource(Res.drawable.ic_info), contentDescription = null, tint = LagarTheme.colors.error, modifier = Modifier.size(20.dp))
            Text(
                text = stringResource(Res.string.home_partial_error),
                style = LagarTheme.type.bodyUi,
                color = LagarTheme.colors.onSurface,
                modifier = Modifier.weight(1f),
            )
            LagarSecondaryButton(onClick = onRetry) { Text(stringResource(Res.string.error_retry)) }
        }
    }
}
