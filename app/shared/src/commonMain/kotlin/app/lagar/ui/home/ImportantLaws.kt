package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.intl.Locale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.toUpperCase
import androidx.compose.ui.unit.dp
import app.lagar.data.ListingItem
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.glass
import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.home_group_acts
import app.lagar.resources.home_group_ordinances
import app.lagar.resources.home_key_laws_subtitle
import app.lagar.resources.home_key_laws_title
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.ic_expand_more
import app.lagar.resources.ic_layer_crown
import app.lagar.resources.layer_fundamental
import app.lagar.settings.UserFocus
import app.lagar.ui.list.StatuteRow
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

private const val WRAP_FONT_SCALE = 1.3f

/** Regeringsformen is the constitution card of the Swedish home. */
internal const val FLAGSHIP_ID = "sfs-1974-152"

/**
 * The order of the "Key laws" groups for a [focus]. Citizens and students get the hierarchy order, fundamental
 * laws first; lawyers, who mostly work with ordinary acts and ordinances, get those first. This is the only effect
 * of the focus on the home so far.
 */
internal fun keyLawGroupOrder(focus: UserFocus): List<DisplayLayer> = when (focus) {
    UserFocus.Citizen, UserFocus.Student -> listOf(DisplayLayer.Fundamental, DisplayLayer.SfsAct, DisplayLayer.SfsOrdinance)
    UserFocus.Lawyer -> listOf(DisplayLayer.SfsAct, DisplayLayer.SfsOrdinance, DisplayLayer.Fundamental)
}

/**
 * "Key laws": a crown medallion and title, the highlighted constitution card, then expandable groups of
 * documents in the order of [keyLawGroupOrder]. Groups with no documents are left out; two groups share a row
 * as in the reference, and one is open at a time.
 */
@Composable
internal fun ImportantLaws(data: HomeData, focus: UserFocus, onOpenDocument: (String) -> Unit, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    val layers = LagarTheme.layers
    val key = LayerKey.Fundamental
    var open by rememberSaveable { mutableStateOf<String?>(null) }
    val groups = keyLawGroupOrder(focus).map { it to data.items(it) }.filter { it.second.isNotEmpty() }
    // Two headers per row stop fitting once the font is large; a header would break mid-word.
    val sideBySide = groups.size >= 2 && LocalDensity.current.fontScale <= WRAP_FONT_SCALE
    val rows = if (sideBySide) listOf(groups.take(2)) + groups.drop(2).map { listOf(it) } else groups.map { listOf(it) }
    val flagship = data.fundamental.firstOrNull { it.id == FLAGSHIP_ID }

    Column(modifier, verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
        Column(Modifier.fillMaxWidth().padding(bottom = spacing.xs), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
            Box(
                modifier = Modifier.size(44.dp).clip(CircleShape).background(layers.tint(key)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(painterResource(Res.drawable.ic_layer_crown), null, tint = layers.accent(key), modifier = Modifier.size(24.dp))
            }
            Text(stringResource(Res.string.home_key_laws_title), style = LagarTheme.type.headlineSm, color = LagarTheme.colors.onSurface, textAlign = TextAlign.Center)
            Text(
                text = stringResource(Res.string.home_key_laws_subtitle).toUpperCase(Locale.current),
                style = LagarTheme.type.labelSm,
                color = layers.onTint(key),
                textAlign = TextAlign.Center,
            )
        }
        flagship?.let { FlagshipCard(it, onClick = { onOpenDocument(it.id) }) }
        rows.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                row.forEach { (layer, _) ->
                    AccordionHeader(layer, expanded = open == layer.name, onClick = { open = if (open == layer.name) null else layer.name }, Modifier.weight(1f))
                }
            }
            row.firstOrNull { open == it.first.name }?.let { (layer, items) ->
                Column(verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                    items.forEach { StatuteRow(it, layer, onClick = { onOpenDocument(it.id) }) }
                }
            }
        }
    }
}

@Composable
private fun FlagshipCard(item: ListingItem, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    val key = LayerKey.Fundamental
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = layers.tint(key),
        border = BorderStroke(1.5.dp, layers.accent(key)),
    ) {
        Row(
            modifier = Modifier.heightIn(min = 56.dp).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(item.title, style = LagarTheme.type.bodyUi, fontWeight = FontWeight.Bold, color = layers.onTint(key))
                Text(item.number, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
            }
            Icon(painterResource(Res.drawable.ic_chevron_right), null, tint = layers.onTint(key), modifier = Modifier.size(24.dp))
        }
    }
}

@Composable
private fun AccordionHeader(layer: DisplayLayer, expanded: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    Surface(
        onClick = onClick,
        modifier = modifier.glass(
            GlassTier.Card,
            shape = MaterialTheme.shapes.large,
            border = if (expanded) BorderStroke(1.dp, layers.accent(layer.key)) else null,
        ),
        shape = MaterialTheme.shapes.large,
        color = Color.Transparent,
    ) {
        Row(
            modifier = Modifier.heightIn(min = 54.dp).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
        ) {
            Text(
                text = stringResource(layer.groupTitleRes()),
                style = LagarTheme.type.labelMd,
                fontWeight = FontWeight.Bold,
                color = LagarTheme.colors.onSurface,
                modifier = Modifier.weight(1f),
            )
            Icon(
                painterResource(Res.drawable.ic_expand_more),
                contentDescription = null,
                tint = LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.size(24.dp).rotate(if (expanded) 180f else 0f),
            )
        }
    }
}

private fun HomeData.items(layer: DisplayLayer): List<ListingItem> = when (layer) {
    DisplayLayer.Fundamental -> fundamental
    DisplayLayer.SfsAct -> acts
    DisplayLayer.SfsOrdinance -> ordinances
    else -> emptyList()
}

/** Short accordion titles: "Acts" and "Ordinances" rather than the SFS-prefixed layer names. */
private fun DisplayLayer.groupTitleRes(): StringResource = when (this) {
    DisplayLayer.Fundamental -> Res.string.layer_fundamental
    DisplayLayer.SfsAct -> Res.string.home_group_acts
    else -> Res.string.home_group_ordinances
}
