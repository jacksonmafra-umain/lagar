package app.lagar.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.painterResource

/** Centered icon, title and short text; used for layers and tabs that have nothing to show yet. */
@Composable
fun EmptyState(icon: DrawableResource, title: String, text: String, modifier: Modifier = Modifier) {
    StatusMessage(icon, title, text, LagarTheme.colors.onSurfaceVariant, modifier)
}

@Composable
internal fun StatusMessage(
    icon: DrawableResource,
    title: String,
    text: String,
    iconTint: Color,
    modifier: Modifier = Modifier,
    action: @Composable (() -> Unit)? = null,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = LagarTheme.spacing.xl, vertical = LagarTheme.spacing.lg),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Box(
            modifier = Modifier.size(64.dp).clip(CircleShape).background(LagarTheme.colors.surfaceContainerHigh),
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(icon), contentDescription = null, tint = iconTint, modifier = Modifier.size(32.dp))
        }
        Text(title, style = LagarTheme.type.headlineSm, color = LagarTheme.colors.onSurface, textAlign = TextAlign.Center)
        Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurfaceVariant, textAlign = TextAlign.Center)
        action?.invoke()
    }
}
