package app.lagar.ui.utforska

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.coming_soon
import app.lagar.resources.document_count
import app.lagar.resources.ic_chevron_right
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.descriptionRes
import app.lagar.ui.common.level
import app.lagar.ui.common.nameRes
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

/** A layer in the Utforska list: level, name, short description and count (or "coming soon"). */
@Composable
fun LayerRow(summary: LayerSummary, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    val key = summary.layer.key
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Row(
            modifier = Modifier.heightIn(min = 72.dp).padding(LagarTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
        ) {
            Surface(
                modifier = Modifier.size(40.dp),
                shape = MaterialTheme.shapes.medium,
                color = layers.tint(key),
                border = BorderStroke(1.dp, layers.border(key)),
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text(summary.layer.level.toString(), style = LagarTheme.type.headlineSm, color = layers.onTint(key))
                }
            }
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    text = stringResource(summary.layer.nameRes()),
                    style = LagarTheme.type.headlineSm,
                    color = layers.onTint(key),
                )
                Text(
                    text = stringResource(summary.layer.descriptionRes()),
                    style = LagarTheme.type.labelSm,
                    color = LagarTheme.colors.onSurfaceVariant,
                )
                if (summary.count > 0) {
                    Text(
                        text = pluralStringResource(Res.plurals.document_count, summary.count, summary.count),
                        style = LagarTheme.type.labelMd,
                        color = layers.onTint(key),
                    )
                } else {
                    LayerBadge(summary.layer, stringResource(Res.string.coming_soon), Modifier.padding(top = LagarTheme.spacing.xs))
                }
            }
            Icon(painterResource(Res.drawable.ic_chevron_right), contentDescription = null, tint = layers.onTint(key))
        }
    }
}
