package app.lagar.ui.reader

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextDecoration
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.ic_expand_more
import app.lagar.resources.reader_amendment_in_force
import app.lagar.resources.reader_amendments
import app.lagar.resources.reader_collapsed
import app.lagar.resources.reader_expanded
import app.lagar.resources.reader_open_document
import app.lagar.resources.reader_reprinted_by
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** The collapsible header of the amendment list: "Amendments (n)" and a chevron, one 48dp row. */
@Composable
internal fun AmendmentsToggle(count: Int, expanded: Boolean, onToggle: () -> Unit, modifier: Modifier = Modifier) {
    val colors = LagarTheme.colors
    val state = stringResource(if (expanded) Res.string.reader_expanded else Res.string.reader_collapsed)
    Row(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(MaterialTheme.shapes.small)
            .clickable(role = Role.Button, onClick = onToggle)
            .semantics { stateDescription = state },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(stringResource(Res.string.reader_amendments, count), style = LagarTheme.type.labelMd, color = colors.onSurface)
        Icon(
            painterResource(Res.drawable.ic_expand_more),
            contentDescription = null,
            tint = colors.onSurfaceVariant,
            modifier = Modifier.rotate(if (expanded) 180f else 0f),
        )
    }
}

/**
 * One amending act: number (a link when [documentId] is known), entry into force, title and the register's
 * scope. Without a [documentId] the row is plain text.
 */
@Composable
internal fun AmendmentItem(row: AmendmentRow, documentId: String?, layer: LayerKey, onOpen: (String) -> Unit, modifier: Modifier = Modifier) {
    val colors = LagarTheme.colors
    val spacing = LagarTheme.spacing
    val open = stringResource(Res.string.reader_open_document, row.number)
    val base = modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget).clip(MaterialTheme.shapes.small)
    Column(
        modifier = if (documentId != null) {
            base.clickable(role = Role.Button) { onOpen(documentId) }.semantics { contentDescription = open }
        } else {
            base
        }.padding(vertical = spacing.xs),
        verticalArrangement = Arrangement.spacedBy(spacing.xs),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(spacing.md), verticalAlignment = Alignment.CenterVertically) {
            Citation(row.number, linked = documentId != null, layer = layer)
            row.inForce?.let {
                Text(stringResource(Res.string.reader_amendment_in_force, it), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
            }
        }
        row.title?.let { Text(it, style = LagarTheme.type.bodyUi, color = colors.onSurface) }
        row.scope?.let { Text(it, style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant) }
    }
}

/** "Reprinted by" and the reprint numbers, each a link when its document exists. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun ReprintsItem(numbers: List<String>, links: Map<String, String>, layer: LayerKey, onOpen: (String) -> Unit, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
        Text(stringResource(Res.string.reader_reprinted_by), style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing.xs)) {
            numbers.forEach { number ->
                val id = links[number]
                val open = stringResource(Res.string.reader_open_document, number)
                Box(
                    modifier = Modifier
                        .sizeIn(minWidth = ShellDimens.TouchTarget, minHeight = ShellDimens.TouchTarget)
                        .clip(MaterialTheme.shapes.small)
                        .then(if (id != null) Modifier.clickable(role = Role.Button) { onOpen(id) }.semantics { contentDescription = open } else Modifier)
                        .padding(horizontal = spacing.xs),
                    contentAlignment = Alignment.CenterStart,
                ) { Citation(number, linked = id != null, layer = layer) }
            }
        }
    }
}

/** An SFS number in the citation style; a link takes the layer's AA-safe text color and an underline. */
@Composable
private fun Citation(number: String, linked: Boolean, layer: LayerKey) {
    Text(
        text = number,
        style = LagarTheme.type.codeCitation,
        color = if (linked) LagarTheme.layers.onTint(layer) else LagarTheme.colors.onSurface,
        textDecoration = if (linked) TextDecoration.Underline else null,
    )
}
