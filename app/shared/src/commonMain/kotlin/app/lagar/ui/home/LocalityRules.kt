package app.lagar.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.intl.Locale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.toUpperCase
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.document_count
import app.lagar.resources.home_locality_key_title
import app.lagar.resources.home_locality_none_in_force
import app.lagar.resources.home_locality_subtitle
import app.lagar.ui.list.StatuteRow
import app.lagar.ui.onboarding.iconRes
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

/**
 * The "key rules" of a Region or Kommun home: the scope medallion, a title, the locality and its document count,
 * then the locality's newest regulations in force. Laid out like the national "Key laws" header.
 */
@Composable
internal fun LocalityRules(data: HomeData, name: String, onOpenDocument: (String) -> Unit, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    val layers = LagarTheme.layers
    val key = data.scope.key
    val level = data.layers.firstOrNull() ?: DisplayLayer.Region
    Column(modifier, verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
        Column(
            Modifier.fillMaxWidth().padding(bottom = spacing.xs),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(spacing.xs),
        ) {
            Box(
                modifier = Modifier.size(44.dp).clip(CircleShape).background(layers.tint(key)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(painterResource(data.scope.iconRes()), null, tint = layers.accent(key), modifier = Modifier.size(24.dp))
            }
            Text(
                stringResource(Res.string.home_locality_key_title),
                style = LagarTheme.type.headlineSm,
                color = LagarTheme.colors.onSurface,
                textAlign = TextAlign.Center,
            )
            val count = pluralStringResource(Res.plurals.document_count, data.localityTotal, data.localityTotal)
            Text(
                text = stringResource(Res.string.home_locality_subtitle, name, count).toUpperCase(Locale.current),
                style = LagarTheme.type.labelSm,
                color = layers.onTint(key),
                textAlign = TextAlign.Center,
            )
        }
        if (data.inForce.isEmpty()) {
            Text(
                stringResource(Res.string.home_locality_none_in_force),
                style = LagarTheme.type.bodyUi,
                color = LagarTheme.colors.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        } else {
            data.inForce.forEach { StatuteRow(it, level, onClick = { onOpenDocument(it.id) }) }
        }
    }
}
