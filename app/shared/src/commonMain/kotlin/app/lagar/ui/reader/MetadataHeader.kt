package app.lagar.ui.reader

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.UriHandler
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import app.lagar.data.DocumentMeta
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.domain.DisplayLayer
import app.lagar.domain.ministryName
import app.lagar.resources.Res
import app.lagar.resources.ic_history
import app.lagar.resources.meta_amended_through
import app.lagar.resources.meta_in_force
import app.lagar.resources.meta_in_force_since
import app.lagar.resources.meta_issued
import app.lagar.resources.meta_ministry
import app.lagar.resources.meta_repealed_banner
import app.lagar.resources.meta_source
import app.lagar.resources.meta_status
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.RepealedBadge
import app.lagar.ui.common.nameRes
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/**
 * Layer badge, number, title and the document's facts. A repealed document shows the Repealed badge
 * and the repeal date; otherwise it is "In force", with the date when the API has one. A repealed
 * document also gets the Repealed layer color, a struck-through number and title and a banner.
 */
@Composable
internal fun MetadataHeader(meta: DocumentMeta, modifier: Modifier = Modifier) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        DocumentTitle(meta)
        DocumentFacts(meta)
        HorizontalDivider(modifier = Modifier.padding(top = LagarTheme.spacing.xs), color = LagarTheme.colors.outlineVariant)
    }
}

/** The layer badge, number and title: the top of [MetadataHeader], and on desktop the top of the text beside the inspector. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun DocumentTitle(meta: DocumentMeta, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    val layers = LagarTheme.layers
    val colors = LagarTheme.colors
    val layer = DisplayLayer.fromRoute(meta.layer, meta.type)
    val repealed = meta.repealed
    val decoration = if (repealed != null) TextDecoration.LineThrough else null
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            verticalArrangement = Arrangement.spacedBy(spacing.xs),
            itemVerticalAlignment = Alignment.CenterVertically,
        ) {
            if (layer != null) LayerBadge(if (repealed != null) LayerKey.Repealed else layer.key, stringResource(layer.nameRes()))
            Text(
                text = meta.number,
                style = LagarTheme.type.codeCitation,
                color = when {
                    repealed != null -> layers.onTint(LayerKey.Repealed)
                    layer != null -> layers.onTint(layer.key)
                    else -> colors.onSurfaceVariant
                },
                textDecoration = decoration,
            )
        }
        Text(
            text = meta.title,
            style = LagarTheme.type.headlineMd,
            color = if (repealed != null) colors.onSurfaceVariant else colors.onSurface,
            textDecoration = decoration,
        )
    }
}

/** The repeal banner, the facts and the source link: the rest of [MetadataHeader], and on desktop the top of the inspector. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun DocumentFacts(meta: DocumentMeta, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    val repealed = meta.repealed
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
        if (repealed != null) RepealedBanner(repealed)
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(spacing.lg),
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            meta.issued?.let { Fact(stringResource(Res.string.meta_issued)) { FactText(it) } }
            ministryName(meta.ministry)?.let { Fact(stringResource(Res.string.meta_ministry)) { FactText(it) } }
            Fact(stringResource(Res.string.meta_status)) {
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
        TextButton(onClick = { openSource(uriHandler, meta.source) }) {
            Text(stringResource(Res.string.meta_source), style = LagarTheme.type.labelMd)
        }
    }
}

/** Full-width notice in the Repealed layer colors, with the history icon so color is not the only signal. */
@Composable
private fun RepealedBanner(date: String) {
    val layers = LagarTheme.layers
    val key = LayerKey.Repealed
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.medium,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Icon(painterResource(Res.drawable.ic_history), contentDescription = null, tint = layers.onTint(key), modifier = Modifier.size(20.dp))
            Text(stringResource(Res.string.meta_repealed_banner, date), style = LagarTheme.type.bodyUi, color = layers.onTint(key))
        }
    }
}

@Composable
private fun Fact(label: String, value: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
        Text(label, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
        value()
    }
}

@Composable
private fun FactText(text: String) = Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface)

/** Opens the official source; a malformed URL or a missing handler is ignored rather than crashing the reader. */
private fun openSource(uriHandler: UriHandler, url: String) {
    try {
        uriHandler.openUri(url)
    } catch (_: Exception) {
    }
}
