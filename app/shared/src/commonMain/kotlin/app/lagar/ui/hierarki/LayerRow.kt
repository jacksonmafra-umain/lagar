package app.lagar.ui.hierarki

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.coming_soon
import app.lagar.resources.document_count
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.layer_numbered_title
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.descriptionRes
import app.lagar.ui.common.iconRes
import app.lagar.ui.common.level
import app.lagar.ui.common.nameRes
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

/**
 * A layer in the Lager list: icon on the solid layer color, "N. Name" title, one-line
 * description, and a badge with the document count or "coming soon". Title and description
 * wrap instead of truncating once the font scale passes [WRAP_FONT_SCALE].
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LayerRow(summary: LayerSummary, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    val key = summary.layer.key
    val accent = layers.accent(key)
    val maxLines = if (LocalDensity.current.fontScale > WRAP_FONT_SCALE) Int.MAX_VALUE else 1
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Row(
            modifier = Modifier.heightIn(min = 64.dp).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
        ) {
            Box(
                modifier = Modifier.size(40.dp).clip(MaterialTheme.shapes.medium).background(accent),
                contentAlignment = Alignment.Center,
            ) {
                Icon(painterResource(summary.layer.iconRes()), contentDescription = null, tint = accent.iconColor(), modifier = Modifier.size(24.dp))
            }
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
                    itemVerticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = stringResource(Res.string.layer_numbered_title, summary.layer.level, stringResource(summary.layer.nameRes())),
                        style = LagarTheme.type.bodyUi,
                        fontWeight = FontWeight.Bold,
                        color = layers.onTint(key),
                        maxLines = maxLines,
                        overflow = TextOverflow.Ellipsis,
                    )
                    CountBadge(summary)
                }
                Text(
                    text = stringResource(summary.layer.descriptionRes()),
                    style = LagarTheme.type.labelSm,
                    color = LagarTheme.colors.onSurfaceVariant,
                    maxLines = maxLines,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Icon(painterResource(Res.drawable.ic_chevron_right), contentDescription = null, tint = layers.onTint(key))
        }
    }
}

@Composable
private fun CountBadge(summary: LayerSummary) {
    val label = if (summary.count > 0) {
        pluralStringResource(Res.plurals.document_count, summary.count, summary.count)
    } else {
        stringResource(Res.string.coming_soon)
    }
    LayerBadge(summary.layer, label)
}

/** White or near-black, whichever is more legible on this fill (all nine layers clear 3:1 either way). */
internal fun Color.iconColor(): Color = if (luminance() > ICON_SWITCH_LUMINANCE) DarkIcon else Color.White

private val DarkIcon = Color(0xFF14181F)
// Luminance where white and near-black give equal contrast on a fill (about 0.18).
private const val ICON_SWITCH_LUMINANCE = 0.18f
private const val WRAP_FONT_SCALE = 1.3f
