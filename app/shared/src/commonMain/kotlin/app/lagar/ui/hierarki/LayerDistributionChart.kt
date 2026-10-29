package app.lagar.ui.hierarki

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.i18n.formatCount
import app.lagar.ui.common.nameRes
import org.jetbrains.compose.resources.stringResource

/**
 * One stacked bar with a segment per layer that has documents, plus a two-column legend for the
 * same layers. Layers with no documents get no segment; with no documents at all the bar is an
 * empty track.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LayerDistributionChart(summaries: List<LayerSummary>, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    val present = summaries.filter { it.count > 0 }
    Column(
        modifier = modifier.fillMaxWidth()
            .glass(GlassTier.Card, shape = MaterialTheme.shapes.large)
            .padding(LagarTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().height(BarHeight).clip(CircleShape).background(LagarTheme.colors.surfaceContainer),
            horizontalArrangement = Arrangement.spacedBy(SegmentGap),
        ) {
            present.forEach { s ->
                Box(Modifier.weight(s.count.toFloat()).height(BarHeight).background(layers.accent(s.layer.key)))
            }
        }
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            present.forEach { LegendItem(it) }
        }
    }
}

@Composable
private fun LegendItem(summary: LayerSummary) {
    Row(
        modifier = Modifier
            .clip(MaterialTheme.shapes.medium)
            .background(LagarTheme.colors.surfaceContainerLow)
            .padding(LagarTheme.spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Box(Modifier.size(10.dp).clip(CircleShape).background(LagarTheme.layers.accent(summary.layer.key)))
        Text(
            text = stringResource(summary.layer.nameRes()),
            style = LagarTheme.type.labelSm,
            color = LagarTheme.colors.onSurface,
        )
        Text(
            text = formatCount(summary.count),
            style = LagarTheme.type.labelSm,
            color = LagarTheme.colors.onSurfaceVariant,
        )
    }
}

private val BarHeight = 12.dp
private val SegmentGap = 2.dp
