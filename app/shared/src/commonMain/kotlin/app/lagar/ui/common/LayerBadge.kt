package app.lagar.ui.common

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.domain.DisplayLayer

/** Pill in the layer's colors: tint fill, 20% border, label in the AA-safe text color. */
@Composable
fun LayerBadge(layer: DisplayLayer, label: String, modifier: Modifier = Modifier) = LayerBadge(layer.key, label, modifier)

/** Same pill, colored by a bare [key]; scopes use it since they have no single display layer. */
@Composable
fun LayerBadge(key: LayerKey, label: String, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    Surface(
        modifier = modifier,
        shape = CircleShape,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Text(
            text = label,
            style = LagarTheme.type.labelSm,
            color = layers.onTint(key),
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.sm, vertical = 2.dp),
        )
    }
}
