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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.i18n.documentCount
import app.lagar.i18n.formatCount
import app.lagar.resources.Res
import app.lagar.resources.coming_soon
import app.lagar.resources.hierarchy_by_ministry
import app.lagar.resources.hierarchy_by_ministry_a11y
import app.lagar.resources.hierarchy_other_statutes
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.layer_numbered_title
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.authorityRes
import app.lagar.ui.common.examplesRes
import app.lagar.ui.common.iconColor
import app.lagar.ui.common.iconRes
import app.lagar.ui.common.level
import app.lagar.ui.common.nameRes
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

/**
 * A layer in the Lager list, after the Swedish Stitch screen: icon on the solid layer color, "N. Name" title with
 * the authority badge (Riksdag, Regering, ...), a line of well-known examples and the document count or "coming
 * soon". When [onBrowseByMinistry] is given and the layer has documents, a "By ministry" pill opens the ministry
 * view. Text wraps instead of truncating once the font scale passes [WRAP_FONT_SCALE].
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LayerRow(
    summary: LayerSummary,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onBrowseByMinistry: (() -> Unit)? = null,
    selected: Boolean = false,
) {
    val layers = LagarTheme.layers
    val key = summary.layer.key
    val accent = layers.accent(key)
    val maxLines = if (LocalDensity.current.fontScale > WRAP_FONT_SCALE) Int.MAX_VALUE else 2
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().semantics { this.selected = selected },
        shape = MaterialTheme.shapes.large,
        color = layers.tint(key),
        // The layer open in the detail pane of the list-detail layout keeps a solid accent outline.
        border = if (selected) BorderStroke(2.dp, accent) else BorderStroke(1.dp, layers.border(key)),
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
                    verticalArrangement = Arrangement.spacedBy(2.dp),
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
                    LayerBadge(summary.layer, stringResource(summary.layer.authorityRes()))
                }
                Text(
                    text = stringResource(summary.layer.examplesRes()),
                    style = LagarTheme.type.labelSm,
                    color = LagarTheme.colors.onSurfaceVariant,
                    maxLines = maxLines,
                    overflow = TextOverflow.Ellipsis,
                )
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
                    verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
                    itemVerticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = if (summary.count > 0) {
                            documentCount(summary.count)
                        } else {
                            stringResource(Res.string.coming_soon)
                        },
                        style = LagarTheme.type.labelSm,
                        color = layers.onTint(key),
                    )
                    if (summary.otherStatutes > 0) {
                        Text(
                            text = pluralStringResource(Res.plurals.hierarchy_other_statutes, summary.otherStatutes, formatCount(summary.otherStatutes)),
                            style = LagarTheme.type.labelSm,
                            color = LagarTheme.colors.onSurfaceVariant,
                        )
                    }
                    if (onBrowseByMinistry != null && summary.count > 0) {
                        BrowseByMinistryPill(summary, onBrowseByMinistry)
                    }
                }
            }
            Icon(painterResource(Res.drawable.ic_chevron_right), contentDescription = null, tint = layers.onTint(key))
        }
    }
}

/** Secondary action of a layer row, a pill with its own 48dp touch target and a full spoken label. */
@Composable
private fun BrowseByMinistryPill(summary: LayerSummary, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    val key = summary.layer.key
    val description = stringResource(Res.string.hierarchy_by_ministry_a11y, stringResource(summary.layer.nameRes()))
    Surface(
        onClick = onClick,
        modifier = Modifier.semantics { contentDescription = description },
        shape = CircleShape,
        color = LagarTheme.colors.surface.copy(alpha = 0.6f),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Text(
            text = stringResource(Res.string.hierarchy_by_ministry),
            style = LagarTheme.type.labelSm,
            color = layers.onTint(key),
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.sm, vertical = LagarTheme.spacing.xs),
        )
    }
}

private const val WRAP_FONT_SCALE = 1.3f
