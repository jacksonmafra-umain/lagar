package app.lagar.ui.reader

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
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
import app.lagar.data.ServiceSummary
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.reader_services
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/**
 * "Tjänster": the public services based on the open document, one row each in the service layer colours. Titles and
 * issuers stay Swedish as the responsible body publishes them. The caller hides the section when [services] is empty.
 */
@Composable
internal fun ServicesSection(services: List<ServiceSummary>, onOpenService: (String) -> Unit, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        PaneHeading(stringResource(Res.string.reader_services))
        services.forEach { service -> ServiceRow(service, onClick = { onOpenService(service.id) }) }
    }
}

@Composable
private fun ServiceRow(service: ServiceSummary, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    val key = LayerKey.Service
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget),
        shape = MaterialTheme.shapes.medium,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
                Text(service.title, style = LagarTheme.type.bodyUi, color = layers.onTint(key))
                Text(service.issuer, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
            }
            Icon(
                painterResource(Res.drawable.ic_chevron_right),
                contentDescription = null,
                tint = layers.onTint(key),
                modifier = Modifier.size(20.dp),
            )
        }
    }
}
