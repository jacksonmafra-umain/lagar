package app.lagar.ui.common

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.ic_history
import app.lagar.resources.repealed
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Neutral-grey pill with a history icon, per the Repealed badge in DESIGN.md. */
@Composable
fun RepealedBadge(modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    val key = LayerKey.Repealed
    Surface(
        modifier = modifier,
        shape = CircleShape,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.sm, vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
        ) {
            Icon(painterResource(Res.drawable.ic_history), contentDescription = null, tint = layers.onTint(key), modifier = Modifier.size(14.dp))
            Text(stringResource(Res.string.repealed), style = LagarTheme.type.labelSm, color = layers.onTint(key))
        }
    }
}
