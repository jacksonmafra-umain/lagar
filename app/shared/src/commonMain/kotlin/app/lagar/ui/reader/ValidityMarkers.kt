package app.lagar.ui.reader

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
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
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.ic_history
import app.lagar.resources.reader_validity_enters_into_force
import app.lagar.resources.reader_validity_expires
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Whether a § wording is the outgoing one ([Expires]) or the incoming one ([EntersIntoForce]). */
enum class ValidityChange { Expires, EntersIntoForce }

/**
 * Riksdagen's note that a § wording stops or starts applying: [condition] is a date (`2031-09-10`) or the
 * condition as published (`den dag som regeringen bestämmer`, `2028-10-01 genom lag (2024:562)`).
 */
data class ValidityMarker(val change: ValidityChange, val condition: String)

/** A § block split into its [marker], if any, and the [text] without it. */
data class StatuteValidity(val marker: ValidityMarker?, val text: String)

// The marker keywords and the change each one announces, as Riksdagen writes them.
private val MARKERS = listOf(
    "Upphör att gälla U:" to ValidityChange.Expires,
    "Träder i kraft I:" to ValidityChange.EntersIntoForce,
)

/**
 * Finds a validity marker right after the bold statute number of [block], e.g.
 * `**5 §** /Upphör att gälla U:den dag som regeringen bestämmer/ Fängelse är ...`, where the same § is printed twice,
 * once per wording. The marker is cut out of the text (`**5 §** Fängelse är ...`) so the reader can show it as a
 * label; the legal text itself is left as it is. A block without a well-formed marker comes back unchanged.
 */
fun statuteValidity(block: String): StatuteValidity {
    val number = STATUTE_START.find(block) ?: return StatuteValidity(null, block)
    val rest = block.substring(number.range.last + 1)
    val opening = rest.trimStart(' ')
    // A few prints double the opening slash: `//Upphör att gälla U:...`.
    val inner = opening.trimStart('/')
    if (inner.length == opening.length || opening.length - inner.length > 2) return StatuteValidity(null, block)
    val (keyword, change) = MARKERS.firstOrNull { inner.startsWith(it.first) } ?: return StatuteValidity(null, block)
    val end = inner.indexOf('/', startIndex = keyword.length)
    if (end < 0) return StatuteValidity(null, block)
    val condition = inner.substring(keyword.length, end).trim().removeSuffix(".").trim()
    if (condition.isEmpty()) return StatuteValidity(null, block)
    val after = inner.substring(end + 1).trimStart(' ')
    val text = if (after.isEmpty() || after.startsWith('\n')) number.value + after else number.value + " " + after
    return StatuteValidity(ValidityMarker(change, condition), text)
}

/**
 * The [marker] of a § card as a chip above its text: the outgoing wording in the neutral Repealed colors with the
 * history icon, the incoming one in the document's [layer] colors. The condition is shown as published.
 */
@Composable
internal fun ValidityLabel(marker: ValidityMarker, layer: LayerKey, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    val key = if (marker.change == ValidityChange.Expires) LayerKey.Repealed else layer
    val label = when (marker.change) {
        ValidityChange.Expires -> stringResource(Res.string.reader_validity_expires, marker.condition)
        ValidityChange.EntersIntoForce -> stringResource(Res.string.reader_validity_enters_into_force, marker.condition)
    }
    Surface(
        modifier = modifier,
        shape = MaterialTheme.shapes.small,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.sm, vertical = LagarTheme.spacing.xs),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
        ) {
            if (marker.change == ValidityChange.Expires) {
                Icon(painterResource(Res.drawable.ic_history), contentDescription = null, tint = layers.onTint(key), modifier = Modifier.size(14.dp))
            }
            Text(label, style = LagarTheme.type.labelSm, color = layers.onTint(key))
        }
    }
}
