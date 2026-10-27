package app.lagar.ui.reader

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import app.lagar.data.DocumentMeta
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.meta_amended_through
import app.lagar.resources.meta_in_force
import app.lagar.resources.meta_in_force_since
import app.lagar.resources.meta_issued
import app.lagar.resources.meta_ministry
import app.lagar.resources.meta_source
import app.lagar.resources.meta_status
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.RepealedBadge
import app.lagar.ui.common.nameRes
import org.jetbrains.compose.resources.stringResource

/**
 * Layer badge, number, title and the document's facts. A repealed document shows the Repealed badge
 * and the repeal date; otherwise it is "In force", with the date when the API has one.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun MetadataHeader(meta: DocumentMeta, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    val layers = LagarTheme.layers
    val colors = LagarTheme.colors
    val layer = DisplayLayer.fromRoute(meta.layer, meta.type)
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            verticalArrangement = Arrangement.spacedBy(spacing.xs),
            itemVerticalAlignment = Alignment.CenterVertically,
        ) {
            if (layer != null) LayerBadge(layer, stringResource(layer.nameRes()))
            Text(
                text = meta.number,
                style = LagarTheme.type.codeCitation,
                color = if (layer != null) layers.onTint(layer.key) else colors.onSurfaceVariant,
            )
        }
        Text(meta.title, style = LagarTheme.type.headlineMd, color = colors.onSurface)
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(spacing.lg),
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            meta.issued?.let { Fact(stringResource(Res.string.meta_issued)) { FactText(it) } }
            meta.ministry?.let { Fact(stringResource(Res.string.meta_ministry)) { FactText(it) } }
            Fact(stringResource(Res.string.meta_status)) {
                val repealed = meta.repealed
                if (repealed != null) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                        RepealedBadge()
                        FactText(repealed)
                    }
                } else {
                    FactText(
                        meta.inForce?.let { stringResource(Res.string.meta_in_force_since, it) }
                            ?: stringResource(Res.string.meta_in_force),
                    )
                }
            }
            meta.amendedThrough?.let { Fact(stringResource(Res.string.meta_amended_through)) { FactText(it) } }
        }
        val uriHandler = LocalUriHandler.current
        TextButton(onClick = { uriHandler.openUri(meta.source) }) {
            Text(stringResource(Res.string.meta_source), style = LagarTheme.type.labelMd)
        }
        HorizontalDivider(modifier = Modifier.padding(top = spacing.xs), color = colors.outlineVariant)
    }
}

@Composable
private fun Fact(label: String, value: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
        value()
    }
}

@Composable
private fun FactText(text: String) = Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface)
