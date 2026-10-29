package app.lagar.ui.reader

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextOverflow
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.bookmark_add
import app.lagar.resources.bookmark_remove
import app.lagar.resources.ic_bookmark
import app.lagar.resources.ic_bookmark_filled
import app.lagar.resources.ic_link
import app.lagar.resources.ic_more_vert
import app.lagar.resources.ic_note
import app.lagar.resources.note_delete
import app.lagar.resources.note_label
import app.lagar.resources.note_placeholder
import app.lagar.resources.note_private
import app.lagar.resources.note_save
import app.lagar.resources.reader_note_add
import app.lagar.resources.reader_note_edit
import app.lagar.resources.reader_note_on
import app.lagar.resources.reader_saved_state
import app.lagar.resources.reader_section_actions
import app.lagar.resources.reader_share_link
import app.lagar.ui.common.LagarButton
import app.lagar.ui.common.LagarSecondaryButton
import app.lagar.ui.common.LagarTextField
import app.lagar.ui.common.SheetShape
import app.lagar.ui.common.sheetGlass
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/**
 * The action of a § card or chapter heading: one 48dp button that opens a menu to save the section, write a
 * note on it and share a link to it. A single button keeps the reading column wide on phones; once the section
 * is saved the button shows the filled bookmark in the layer colour, and says so to screen readers.
 */
@Composable
internal fun SectionActions(
    label: String,
    layer: LayerKey,
    saved: Boolean,
    hasNote: Boolean,
    onToggleSave: () -> Unit,
    onNote: () -> Unit,
    onShare: () -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    val description = stringResource(Res.string.reader_section_actions, label)
    val savedState = stringResource(Res.string.reader_saved_state)
    Box {
        Box(
            modifier = Modifier
                .size(ShellDimens.TouchTarget)
                .clip(CircleShape)
                .clickable(role = Role.Button) { open = true }
                .semantics {
                    contentDescription = description
                    if (saved) stateDescription = savedState
                },
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                painterResource(if (saved) Res.drawable.ic_bookmark_filled else Res.drawable.ic_more_vert),
                contentDescription = null,
                tint = if (saved) LagarTheme.layers.onTint(layer) else LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.size(ShellDimens.SmallIconSize),
            )
        }
        DropdownMenu(
            expanded = open,
            onDismissRequest = { open = false },
            shape = MaterialTheme.shapes.medium,
            containerColor = LagarTheme.colors.surfaceContainerHigh,
        ) {
            MenuItem(
                icon = if (saved) Res.drawable.ic_bookmark_filled else Res.drawable.ic_bookmark,
                text = stringResource(if (saved) Res.string.bookmark_remove else Res.string.bookmark_add, label),
                tint = if (saved) LagarTheme.layers.onTint(layer) else LagarTheme.colors.onSurfaceVariant,
            ) {
                open = false
                onToggleSave()
            }
            MenuItem(Res.drawable.ic_note, stringResource(if (hasNote) Res.string.reader_note_edit else Res.string.reader_note_add)) {
                open = false
                onNote()
            }
            MenuItem(Res.drawable.ic_link, stringResource(Res.string.reader_share_link, label)) {
                open = false
                onShare()
            }
        }
    }
}

@Composable
private fun MenuItem(icon: DrawableResource, text: String, tint: Color = LagarTheme.colors.onSurfaceVariant, onClick: () -> Unit) {
    DropdownMenuItem(
        text = { Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface) },
        onClick = onClick,
        leadingIcon = { Icon(painterResource(icon), contentDescription = null, tint = tint, modifier = Modifier.size(ShellDimens.SmallIconSize)) },
        modifier = Modifier.heightIn(min = ShellDimens.TouchTarget),
    )
}

/** A saved note under a § or the document header: the layer `tint` panel with the note text; a tap edits it. */
@Composable
internal fun NoteChip(text: String, layer: LayerKey, onEdit: () -> Unit, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    val shape = MaterialTheme.shapes.small
    val spacing = LagarTheme.spacing
    Row(
        modifier = modifier
            .fillMaxWidth()
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(shape)
            .background(layers.tint(layer))
            .border(ShellDimens.Hairline, layers.border(layer), shape)
            .clickable(role = Role.Button, onClickLabel = stringResource(Res.string.reader_note_edit), onClick = onEdit)
            .padding(horizontal = spacing.sm, vertical = spacing.xs),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(spacing.sm),
    ) {
        Icon(
            painterResource(Res.drawable.ic_note),
            contentDescription = stringResource(Res.string.note_label),
            tint = layers.onTint(layer),
            modifier = Modifier.size(ShellDimens.SmallIconSize),
        )
        Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface, maxLines = NOTE_LINES, overflow = TextOverflow.Ellipsis)
    }
}

/** The document note under the reader header: the note when there is one, otherwise an "Add note" action. */
@Composable
internal fun DocumentNote(text: String?, layer: LayerKey, onEdit: () -> Unit, modifier: Modifier = Modifier) {
    if (text != null) {
        NoteChip(text, layer, onEdit, modifier)
        return
    }
    Row(
        modifier = modifier
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(MaterialTheme.shapes.small)
            .clickable(role = Role.Button, onClick = onEdit)
            .padding(horizontal = LagarTheme.spacing.xs),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Icon(painterResource(Res.drawable.ic_note), contentDescription = null, tint = LagarTheme.layers.onTint(layer), modifier = Modifier.size(ShellDimens.SmallIconSize))
        Text(stringResource(Res.string.reader_note_add), style = LagarTheme.type.labelMd, color = LagarTheme.layers.onTint(layer))
    }
}

/**
 * Writes or edits the private note on [target] (a § label or the document title). Saving blank text deletes an
 * existing note; [onDelete] is null for a new note.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun NoteEditorSheet(
    target: String,
    initial: String,
    onSave: (String) -> Unit,
    onDelete: (() -> Unit)?,
    onDismiss: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    var text by rememberSaveable(target) { mutableStateOf(initial) }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        modifier = Modifier.sheetGlass(SheetShape),
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        shape = SheetShape,
        containerColor = Color.Transparent,
        contentColor = LagarTheme.colors.onSurface,
    ) {
        Column(
            modifier = Modifier.padding(start = spacing.marginMobile, end = spacing.marginMobile, bottom = bottom + spacing.lg),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            Text(
                text = stringResource(Res.string.reader_note_on, target),
                style = LagarTheme.type.headlineSm,
                color = LagarTheme.colors.onSurface,
                modifier = Modifier.semantics { heading() },
            )
            LagarTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.fillMaxWidth(),
                label = stringResource(Res.string.note_label),
                placeholder = stringResource(Res.string.note_placeholder),
                singleLine = false,
                minLines = EDITOR_LINES,
            )
            Text(stringResource(Res.string.note_private), style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
            Row(Modifier.align(Alignment.End), horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                if (onDelete != null) {
                    LagarSecondaryButton(onClick = onDelete, contentColor = LagarTheme.colors.error) {
                        Text(stringResource(Res.string.note_delete), style = LagarTheme.type.labelMd)
                    }
                }
                LagarButton(onClick = { onSave(text) }, enabled = text.isNotBlank() || onDelete != null) {
                    Text(stringResource(Res.string.note_save), style = LagarTheme.type.labelMd)
                }
            }
        }
    }
}

private const val NOTE_LINES = 4
private const val EDITOR_LINES = 4
