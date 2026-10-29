package app.lagar.ui.hierarki

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.i18n.documentCount
import app.lagar.resources.Res
import app.lagar.resources.coming_soon
import app.lagar.ui.common.level
import app.lagar.ui.common.nameRes
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.stringResource

/**
 * Nine stacked bands in hierarchy order: Fundamental laws narrowest at the top, services widest at
 * the bottom. Width follows the level, never the document count.
 */
@Composable
fun NormPyramid(summaries: List<LayerSummary>, onBandClick: (LayerSummary) -> Unit, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
    ) {
        summaries.forEach { s ->
            val width = TOP_WIDTH + (1f - TOP_WIDTH) * (s.layer.level - 1) / (summaries.size - 1)
            Band(s, onClick = { onBandClick(s) }, modifier = Modifier.fillMaxWidth(width))
        }
    }
}

@Composable
private fun Band(summary: LayerSummary, onClick: () -> Unit, modifier: Modifier) {
    val layers = LagarTheme.layers
    val key = summary.layer.key
    // The narrow upper bands cannot hold a 200% label, so band text caps at 1.3x.
    val density = LocalDensity.current
    CompositionLocalProvider(LocalDensity provides Density(density.density, fontScale = minOf(density.fontScale, MAX_FONT_SCALE))) {
        Surface(
            onClick = onClick,
            modifier = modifier,
            shape = MaterialTheme.shapes.medium,
            color = layers.tint(key),
            border = BorderStroke(1.dp, layers.border(key)),
        ) {
            Column(
                modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).padding(horizontal = LagarTheme.spacing.sm, vertical = LagarTheme.spacing.xs),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(
                    text = stringResource(summary.layer.nameRes()),
                    style = LagarTheme.type.labelMd,
                    color = layers.onTint(key),
                    textAlign = TextAlign.Center,
                )
                if (summary.count > 0) {
                    Text(
                        text = documentCount(summary.count),
                        style = LagarTheme.type.labelSm,
                        color = layers.onTint(key),
                        textAlign = TextAlign.Center,
                    )
                } else {
                    Text(
                        text = stringResource(Res.string.coming_soon),
                        style = LagarTheme.type.labelSm,
                        color = LagarTheme.colors.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }
}

private const val TOP_WIDTH = 0.5f
private const val MAX_FONT_SCALE = 1.3f
