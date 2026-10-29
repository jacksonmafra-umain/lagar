package app.lagar.ui.list

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.data.ListingItem
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.glass
import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.ic_chevron_right
import app.lagar.ui.common.RepealedBadge
import org.jetbrains.compose.resources.painterResource

/**
 * One document: a 3dp layer indicator, the number in code-citation style, the title (two lines at
 * most) and the year issued. A repealed document switches to the neutral Repealed layer with a
 * badge, a history icon and a struck-through title, so color is never the only signal.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun StatuteRow(item: ListingItem, layer: DisplayLayer?, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    val repealed = item.repealed != null
    val key = if (repealed) LayerKey.Repealed else (layer?.key ?: LayerKey.Repealed)
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().glass(GlassTier.Card, shape = MaterialTheme.shapes.medium),
        shape = MaterialTheme.shapes.medium,
        color = Color.Transparent,
    ) {
        Row(Modifier.height(IntrinsicSize.Min)) {
            Box(Modifier.width(3.dp).fillMaxHeight().background(layers.accent(key)))
            Column(
                modifier = Modifier.weight(1f).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
                verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
            ) {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
                    itemVerticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = item.number,
                        style = LagarTheme.type.codeCitation,
                        color = layers.onTint(key),
                        textDecoration = if (repealed) TextDecoration.LineThrough else null,
                    )
                    if (repealed) RepealedBadge()
                }
                Text(
                    text = item.title,
                    style = LagarTheme.type.bodyUi,
                    color = if (repealed) LagarTheme.colors.onSurfaceVariant else LagarTheme.colors.onSurface,
                    textDecoration = if (repealed) TextDecoration.LineThrough else null,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                item.issued?.take(YEAR_LENGTH)?.let {
                    Text(it, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
                }
            }
            Icon(
                painterResource(Res.drawable.ic_chevron_right),
                contentDescription = null,
                tint = LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.align(Alignment.CenterVertically).padding(end = LagarTheme.spacing.sm),
            )
        }
    }
}

private const val YEAR_LENGTH = 4
