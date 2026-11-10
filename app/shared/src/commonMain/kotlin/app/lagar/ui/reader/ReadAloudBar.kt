package app.lagar.ui.reader

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.ic_close
import app.lagar.resources.ic_pause
import app.lagar.resources.ic_play
import app.lagar.resources.ic_skip_next
import app.lagar.resources.ic_skip_previous
import app.lagar.resources.ic_tune
import app.lagar.resources.reader_read_aloud_close
import app.lagar.resources.reader_read_aloud_next
import app.lagar.resources.reader_read_aloud_now
import app.lagar.resources.reader_read_aloud_pause
import app.lagar.resources.reader_read_aloud_play
import app.lagar.resources.reader_read_aloud_previous
import app.lagar.resources.reader_read_aloud_settings
import app.lagar.resources.reader_read_aloud_text
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** The widest the player gets; on phones it takes the width between the margins. */
private val BarMaxWidth = 560.dp

/**
 * The read-aloud player over the bottom of the reader, on bar glass: the § being read ([label], or the plain "reading
 * aloud" for text before the first §), previous, play or pause, next, the voice settings and close.
 */
@Composable
internal fun ReadAloudBar(
    label: String?,
    playing: Boolean,
    hazeState: HazeState,
    accent: Color,
    onPrevious: () -> Unit,
    onToggle: () -> Unit,
    onNext: () -> Unit,
    onSettings: () -> Unit,
    onClose: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val spacing = LagarTheme.spacing
    Row(
        modifier = modifier
            .widthIn(max = BarMaxWidth)
            .fillMaxWidth()
            .glass(GlassTier.Bar, hazeState, shape = RoundedCornerShape(28.dp))
            .padding(horizontal = spacing.xs, vertical = spacing.xs),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            text = if (label != null) stringResource(Res.string.reader_read_aloud_now, label) else stringResource(Res.string.reader_read_aloud_text),
            style = LagarTheme.type.labelMd,
            color = LagarTheme.colors.onSurface,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier
                .weight(1f)
                .padding(start = spacing.sm)
                .semantics { liveRegion = LiveRegionMode.Polite },
        )
        PlayerButton(painterResource(Res.drawable.ic_skip_previous), stringResource(Res.string.reader_read_aloud_previous), onClick = onPrevious)
        PlayerButton(
            icon = painterResource(if (playing) Res.drawable.ic_pause else Res.drawable.ic_play),
            description = stringResource(if (playing) Res.string.reader_read_aloud_pause else Res.string.reader_read_aloud_play),
            tint = accent,
            onClick = onToggle,
        )
        PlayerButton(painterResource(Res.drawable.ic_skip_next), stringResource(Res.string.reader_read_aloud_next), onClick = onNext)
        PlayerButton(painterResource(Res.drawable.ic_tune), stringResource(Res.string.reader_read_aloud_settings), onClick = onSettings)
        PlayerButton(painterResource(Res.drawable.ic_close), stringResource(Res.string.reader_read_aloud_close), onClick = onClose)
    }
}

@Composable
private fun PlayerButton(icon: Painter, description: String, tint: Color = LagarTheme.colors.onSurfaceVariant, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(ShellDimens.IconSize))
    }
}
