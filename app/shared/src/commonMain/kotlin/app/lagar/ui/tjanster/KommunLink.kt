package app.lagar.ui.tjanster

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.UriHandler
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.ic_link
import app.lagar.resources.services_kommun_link
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/**
 * "Hos <kommun>": opens the chosen kommun's website in the system browser. Template kommun services link to the
 * kommun's home page, not a deep link (see the Tjänster design). Draws nothing unless [place] is a kommun with a name
 * and a website, so a kommun missing from `kommuner.json` or no kommun chosen never shows a dead button.
 */
@Composable
fun KommunLink(place: ServicePlace, modifier: Modifier = Modifier) {
    val kommun = place as? ServicePlace.Kommun ?: return
    val name = kommun.name ?: return
    val website = kommun.website ?: return
    val uriHandler = LocalUriHandler.current
    val color = LagarTheme.layers.onTint(LayerKey.Service)
    TextButton(onClick = { openWebsite(uriHandler, website) }, modifier = modifier) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
            Icon(painterResource(Res.drawable.ic_link), contentDescription = null, tint = color, modifier = Modifier.size(16.dp))
            Text(stringResource(Res.string.services_kommun_link, name), style = LagarTheme.type.labelMd, color = color)
        }
    }
}

/** Opens [url]; a malformed URL or a missing handler is ignored rather than crashing the list, as in the reader. */
private fun openWebsite(uriHandler: UriHandler, url: String) {
    try {
        uriHandler.openUri(url)
    } catch (_: Exception) {
    }
}
