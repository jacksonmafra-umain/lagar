package app.lagar.ui.common

import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.error_retry
import app.lagar.resources.error_text
import app.lagar.resources.error_title
import app.lagar.resources.ic_info
import org.jetbrains.compose.resources.stringResource

/** Designed failure state with a retry button; shown instead of a spinner or a crash. */
@Composable
fun ErrorState(onRetry: () -> Unit, modifier: Modifier = Modifier) {
    StatusMessage(
        icon = Res.drawable.ic_info,
        title = stringResource(Res.string.error_title),
        text = stringResource(Res.string.error_text),
        iconTint = LagarTheme.colors.error,
        modifier = modifier,
        action = { Button(onClick = onRetry) { Text(stringResource(Res.string.error_retry)) } },
    )
}
