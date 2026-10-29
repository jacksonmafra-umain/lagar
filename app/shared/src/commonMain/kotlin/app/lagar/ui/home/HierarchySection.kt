package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.i18n.documentCount
import app.lagar.i18n.formatCount
import app.lagar.resources.Res
import app.lagar.resources.coming_soon
import app.lagar.resources.explore_distribution_title
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.layer_card_open
import app.lagar.resources.layer_level
import app.lagar.resources.layer_numbered_title
import app.lagar.resources.wide_distribution_direction
import app.lagar.resources.wide_hierarchy_eyebrow
import app.lagar.resources.wide_hierarchy_text
import app.lagar.resources.wide_hierarchy_title
import app.lagar.resources.wide_total_documents
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.descriptionRes
import app.lagar.ui.common.iconColor
import app.lagar.ui.common.iconRes
import app.lagar.ui.common.level
import app.lagar.ui.common.nameRes
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

private const val GRID_COLUMNS = 3

/** "Sweden's hierarchy of norms": heading with the total, the distribution bar and a grid of the nine levels. */
@Composable
internal fun HierarchySection(counts: Map<DisplayLayer, Int>, onLayerClick: (DisplayLayer) -> Unit) {
    val colors = LagarTheme.colors
    val spacing = LagarTheme.spacing
    val total = counts.values.sum()
    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(spacing.lg)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
            Eyebrow(stringResource(Res.string.wide_hierarchy_eyebrow))
            Text(stringResource(Res.string.wide_hierarchy_title), style = LagarTheme.type.headlineMd, color = colors.onSurface)
            Text(
                stringResource(Res.string.wide_hierarchy_text),
                style = LagarTheme.type.bodyUi,
                color = colors.onSurfaceVariant,
                modifier = Modifier.widthIn(max = 720.dp),
            )
        }
        Surface(shape = MaterialTheme.shapes.large, color = colors.surfaceContainerLowest, border = BorderStroke(1.dp, colors.outlineVariant)) {
            Column(Modifier.padding(horizontal = spacing.md, vertical = spacing.sm), horizontalAlignment = Alignment.End) {
                Text(formatCount(total), style = LagarTheme.type.headlineMd, fontWeight = FontWeight.Bold, color = colors.onSurface)
                Text(stringResource(Res.string.wide_total_documents), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
            }
        }
    }
    DistributionBar(counts)
    Column(verticalArrangement = Arrangement.spacedBy(spacing.md)) {
        DisplayLayer.entries.chunked(GRID_COLUMNS).forEach { row ->
            Row(Modifier.height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(spacing.md)) {
                row.forEach { layer ->
                    LayerCard(layer, counts[layer] ?: 0, onClick = { onLayerClick(layer) }, modifier = Modifier.weight(1f).fillMaxHeight())
                }
            }
        }
    }
}

/** One segment per level with documents, sized by its count, in hierarchy order. */
@Composable
private fun DistributionBar(counts: Map<DisplayLayer, Int>) {
    val colors = LagarTheme.colors
    val present = DisplayLayer.entries.filter { (counts[it] ?: 0) > 0 }
    Surface(shape = MaterialTheme.shapes.large, color = colors.surfaceContainerLowest, border = BorderStroke(1.dp, colors.outlineVariant)) {
        Column(Modifier.padding(LagarTheme.spacing.md), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(stringResource(Res.string.explore_distribution_title), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
                Text(stringResource(Res.string.wide_distribution_direction), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
            }
            Row(
                modifier = Modifier.fillMaxWidth().height(12.dp).clip(CircleShape).background(colors.surfaceContainer),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                present.forEach { layer ->
                    Box(Modifier.weight((counts[layer] ?: 0).toFloat()).fillMaxHeight().background(LagarTheme.layers.accent(layer.key)))
                }
            }
        }
    }
}

/** Icon, level badge, numbered name, description, then the count and "Browse", or "Coming soon" when empty. */
@Composable
private fun LayerCard(layer: DisplayLayer, count: Int, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val colors = LagarTheme.colors
    val layers = LagarTheme.layers
    val spacing = LagarTheme.spacing
    val accent = layers.accent(layer.key)
    Surface(
        onClick = onClick,
        modifier = modifier,
        shape = MaterialTheme.shapes.large,
        color = colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, colors.outlineVariant),
    ) {
        Column(Modifier.padding(spacing.md), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                Box(Modifier.size(40.dp).clip(CircleShape).background(accent), contentAlignment = Alignment.Center) {
                    Icon(painterResource(layer.iconRes()), null, tint = accent.iconColor(), modifier = Modifier.size(22.dp))
                }
                LayerBadge(layer, stringResource(Res.string.layer_level, layer.level))
            }
            Text(
                stringResource(Res.string.layer_numbered_title, layer.level, stringResource(layer.nameRes())),
                style = LagarTheme.type.headlineSm,
                color = colors.onSurface,
            )
            Text(stringResource(layer.descriptionRes()), style = LagarTheme.type.bodyUi, color = colors.onSurfaceVariant)
            Spacer(Modifier.weight(1f))
            HorizontalDivider(color = colors.outlineVariant)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (count > 0) documentCount(count) else stringResource(Res.string.coming_soon),
                    style = LagarTheme.type.labelMd,
                    fontWeight = FontWeight.Bold,
                    color = if (count > 0) colors.onSurface else colors.onSurfaceVariant,
                )
                if (count > 0) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(Res.string.layer_card_open), style = LagarTheme.type.labelMd, color = layers.onTint(layer.key))
                        Icon(
                            painterResource(Res.drawable.ic_chevron_right),
                            null,
                            tint = layers.onTint(layer.key),
                            modifier = Modifier.size(18.dp),
                        )
                    }
                }
            }
        }
    }
}
