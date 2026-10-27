package app.lagar.ui.common

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.ui.hierarki.iconColor

/** Pill-shaped tab filled with the accent of [key] when selected. */
@Composable
fun PillTab(text: String, selected: Boolean, key: LayerKey, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    val accent = layers.accent(key)
    // A 32dp pill inside a 48dp hit area.
    Box(
        modifier = Modifier
            .heightIn(min = 48.dp)
            .clip(CircleShape)
            .clickable(onClick = onClick)
            .semantics { role = Role.Tab; this.selected = selected },
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = CircleShape,
            color = if (selected) accent else LagarTheme.colors.surfaceContainerLowest,
            border = BorderStroke(1.dp, if (selected) accent else LagarTheme.colors.outlineVariant),
        ) {
            Text(
                text = text.uppercase(),
                style = LagarTheme.type.labelSm,
                fontWeight = FontWeight.Bold,
                color = if (selected) accent.iconColor() else LagarTheme.colors.onSurface,
                modifier = Modifier.heightIn(min = 32.dp).padding(horizontal = LagarTheme.spacing.md, vertical = 8.dp),
            )
        }
    }
}
