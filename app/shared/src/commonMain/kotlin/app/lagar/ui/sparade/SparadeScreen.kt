package app.lagar.ui.sparade

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.intl.Locale
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.toUpperCase
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.glass
import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.bookmark_remove
import app.lagar.resources.ic_bookmark_filled
import app.lagar.resources.ic_bookmarks
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.ic_delete
import app.lagar.resources.ic_note
import app.lagar.resources.ic_search
import app.lagar.resources.note_delete_on
import app.lagar.resources.note_label
import app.lagar.resources.saved_empty_text
import app.lagar.resources.saved_empty_title
import app.lagar.resources.saved_filter_all
import app.lagar.resources.saved_filter_documents
import app.lagar.resources.saved_filter_notes
import app.lagar.resources.saved_filter_provisions
import app.lagar.resources.saved_group_other
import app.lagar.resources.saved_no_match_text
import app.lagar.resources.saved_no_match_title
import app.lagar.resources.saved_note_deleted
import app.lagar.resources.saved_note_preview
import app.lagar.resources.saved_removed
import app.lagar.resources.saved_search
import app.lagar.resources.saved_undo
import app.lagar.settings.Bookmark
import app.lagar.settings.BookmarkStore
import app.lagar.settings.Note
import app.lagar.settings.NoteStore
import app.lagar.settings.SavedProvision
import app.lagar.settings.toListingItem
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.LagarTextField
import app.lagar.ui.common.PillTab
import app.lagar.ui.common.RepealedBadge
import app.lagar.ui.common.nameRes
import app.lagar.ui.list.StatuteRow
import app.lagar.ui.reader.notePreview
import app.lagar.ui.shell.LocalShellPadding
import app.lagar.ui.shell.ShellDimens
import kotlinx.coroutines.launch
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.getString
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/**
 * Sparade tab: the device-local saved documents, provisions and notes. [onOpen] opens a document, at the
 * provision's anchor when it has one.
 */
@Composable
fun SparadeRoute(
    onOpen: (id: String, anchor: String?) -> Unit,
    store: BookmarkStore = koinInject(),
    noteStore: NoteStore = koinInject(),
) {
    val bookmarks by store.bookmarks.collectAsState()
    val provisions by store.provisions.collectAsState()
    val notes by noteStore.notes.collectAsState()
    SparadeScreen(
        bookmarks = bookmarks,
        provisions = provisions,
        notes = notes,
        onOpen = onOpen,
        onRemove = { entry ->
            when (entry) {
                is SavedEntry.Document -> store.remove(entry.document.id)?.let { removed -> { store.restore(removed) } }
                is SavedEntry.Provision -> store.removeProvision(entry.document.id, entry.provision.anchor)
                    ?.let { removed -> { store.restoreProvision(removed) } }
                is SavedEntry.NoteOnly -> noteStore.delete(entry.document.id, entry.note.anchor)
                    ?.let { removed -> { noteStore.restore(removed) } }
            }
        },
    )
}

/**
 * Saved items grouped by level, with a search field and a kind filter. [onRemove] removes an entry and returns
 * the action that undoes it (offered in a snackbar), or null when there was nothing to remove.
 */
@Composable
fun SparadeScreen(
    bookmarks: List<Bookmark>,
    provisions: List<SavedProvision>,
    notes: List<Note>,
    onOpen: (id: String, anchor: String?) -> Unit,
    onRemove: (SavedEntry) -> (() -> Unit)?,
) {
    val shell = LocalShellPadding.current
    val spacing = LagarTheme.spacing
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf(SavedFilter.All) }
    val groups = remember(bookmarks, provisions, notes, filter, query) { savedGroups(bookmarks, provisions, notes, filter, query) }

    fun remove(entry: SavedEntry) {
        val undo = onRemove(entry) ?: return
        scope.launch {
            val message = when (entry) {
                is SavedEntry.Document -> getString(Res.string.saved_removed, entry.document.title)
                is SavedEntry.Provision -> getString(Res.string.saved_removed, "${entry.provision.label}, ${entry.document.title}")
                is SavedEntry.NoteOnly -> getString(Res.string.saved_note_deleted)
            }
            snackbar.currentSnackbarData?.dismiss()
            val result = snackbar.showSnackbar(message, actionLabel = getString(Res.string.saved_undo), duration = SnackbarDuration.Long)
            if (result == SnackbarResult.ActionPerformed) undo()
        }
    }

    Box(Modifier.fillMaxSize()) {
        if (bookmarks.isEmpty() && provisions.isEmpty() && notes.isEmpty()) {
            Box(Modifier.fillMaxSize().padding(shell), contentAlignment = Alignment.Center) {
                EmptyState(
                    icon = Res.drawable.ic_bookmarks,
                    title = stringResource(Res.string.saved_empty_title),
                    text = stringResource(Res.string.saved_empty_text),
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(
                    start = spacing.marginMobile,
                    end = spacing.marginMobile,
                    top = shell.calculateTopPadding() + spacing.md,
                    bottom = shell.calculateBottomPadding() + spacing.md,
                ),
                verticalArrangement = Arrangement.spacedBy(spacing.sm),
            ) {
                item(key = "search") {
                    LagarTextField(
                        value = query,
                        onValueChange = { query = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = stringResource(Res.string.saved_search),
                        leadingIcon = Res.drawable.ic_search,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    )
                }
                item(key = "filters") {
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                        SavedFilter.entries.forEach { f ->
                            PillTab(stringResource(f.labelRes()), selected = f == filter, key = FILTER_LAYER) { filter = f }
                        }
                    }
                }
                if (groups.isEmpty()) {
                    item(key = "no-match") {
                        EmptyState(
                            icon = Res.drawable.ic_search,
                            title = stringResource(Res.string.saved_no_match_title),
                            text = stringResource(Res.string.saved_no_match_text),
                            modifier = Modifier.fillMaxWidth().padding(vertical = spacing.lg),
                        )
                    }
                }
                groups.forEach { group ->
                    item(key = "group:${group.layer?.name ?: "other"}") { GroupHeading(group.layer) }
                    items(group.entries, key = { it.key }) { entry ->
                        SavedEntryRow(entry, onOpen, onRemove = { remove(entry) })
                    }
                }
            }
        }
        SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter).padding(bottom = shell.calculateBottomPadding()))
    }
}

private fun SavedFilter.labelRes(): StringResource = when (this) {
    SavedFilter.All -> Res.string.saved_filter_all
    SavedFilter.Documents -> Res.string.saved_filter_documents
    SavedFilter.Provisions -> Res.string.saved_filter_provisions
    SavedFilter.Notes -> Res.string.saved_filter_notes
}

/** A level heading: a 10dp layer dot and the level name in bold upper-case `labelSm`. */
@Composable
private fun GroupHeading(layer: DisplayLayer?) {
    val name = stringResource(layer?.nameRes() ?: Res.string.saved_group_other)
    Row(
        modifier = Modifier.padding(top = LagarTheme.spacing.sm).semantics(mergeDescendants = true) { heading() },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Box(Modifier.size(10.dp).clip(CircleShape).background(LagarTheme.layers.accent(layer?.key ?: LayerKey.Repealed)))
        Text(
            name.toUpperCase(Locale.current),
            style = LagarTheme.type.labelSm,
            fontWeight = FontWeight.Bold,
            color = LagarTheme.colors.onSurfaceVariant,
        )
    }
}

@Composable
private fun SavedEntryRow(entry: SavedEntry, onOpen: (String, String?) -> Unit, onRemove: () -> Unit) {
    val document = entry.document
    val layer = document.displayLayer
    val key = if (document.repealed != null) LayerKey.Repealed else (layer?.key ?: LayerKey.Repealed)
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
        val cardModifier = Modifier.weight(1f)
        when (entry) {
            is SavedEntry.Document -> StatuteRow(
                item = document.toListingItem(),
                layer = layer,
                onClick = { onOpen(document.id, null) },
                modifier = cardModifier,
                note = entry.note?.let { stringResource(Res.string.saved_note_preview, notePreview(it.text)) },
            )
            is SavedEntry.Provision -> SavedCard(key, onClick = { onOpen(document.id, entry.provision.anchor) }, modifier = cardModifier) {
                Heading(entry.provision.label, key, repealed = document.repealed != null)
                DocumentTitle(document.title, repealed = document.repealed != null)
                if (entry.provision.excerpt.isNotEmpty()) {
                    Text(
                        entry.provision.excerpt,
                        style = LagarTheme.type.bodyLegalMd,
                        color = LagarTheme.colors.onSurface,
                        maxLines = EXCERPT_LINES,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                entry.note?.let {
                    Text(
                        stringResource(Res.string.saved_note_preview, notePreview(it.text)),
                        style = LagarTheme.type.labelSm,
                        color = LagarTheme.layers.onTint(key),
                        maxLines = NOTE_PREVIEW_LINES,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            is SavedEntry.NoteOnly -> SavedCard(key, onClick = { onOpen(document.id, entry.note.anchor) }, modifier = cardModifier) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
                    Icon(
                        painterResource(Res.drawable.ic_note),
                        contentDescription = stringResource(Res.string.note_label),
                        tint = LagarTheme.layers.onTint(key),
                        modifier = Modifier.size(ShellDimens.SmallIconSize),
                    )
                    Heading(entry.note.label ?: document.number, key, repealed = document.repealed != null)
                }
                DocumentTitle(document.title, repealed = document.repealed != null)
                Text(entry.note.text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface, maxLines = NOTE_LINES, overflow = TextOverflow.Ellipsis)
            }
        }
        when (entry) {
            is SavedEntry.Document -> RemoveButton(
                painterResource(Res.drawable.ic_bookmark_filled),
                LagarTheme.layers.onTint(layer?.key ?: LayerKey.SfsAct),
                stringResource(Res.string.bookmark_remove, document.title),
                onRemove,
            )
            is SavedEntry.Provision -> RemoveButton(
                painterResource(Res.drawable.ic_bookmark_filled),
                LagarTheme.layers.onTint(layer?.key ?: LayerKey.SfsAct),
                stringResource(Res.string.bookmark_remove, "${entry.provision.label}, ${document.title}"),
                onRemove,
            )
            is SavedEntry.NoteOnly -> RemoveButton(
                painterResource(Res.drawable.ic_delete),
                LagarTheme.colors.onSurfaceVariant,
                stringResource(Res.string.note_delete_on, entry.note.label?.let { "$it, ${document.title}" } ?: document.title),
                onRemove,
            )
        }
    }
}

/** The § label (or document number) in code-citation style, struck through with a badge when repealed. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Heading(text: String, key: LayerKey, repealed: Boolean) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm), itemVerticalAlignment = Alignment.CenterVertically) {
        Text(
            text,
            style = LagarTheme.type.codeCitation,
            color = LagarTheme.layers.onTint(key),
            textDecoration = if (repealed) TextDecoration.LineThrough else null,
        )
        if (repealed) RepealedBadge()
    }
}

@Composable
private fun DocumentTitle(title: String, repealed: Boolean) {
    Text(
        title,
        style = LagarTheme.type.labelSm,
        color = LagarTheme.colors.onSurfaceVariant,
        textDecoration = if (repealed) TextDecoration.LineThrough else null,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
    )
}

/** A saved provision or note: the `StatuteRow` card shape with a 3dp layer indicator and a chevron. */
@Composable
private fun SavedCard(key: LayerKey, onClick: () -> Unit, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().glass(GlassTier.Card, shape = MaterialTheme.shapes.medium),
        shape = MaterialTheme.shapes.medium,
        color = Color.Transparent,
    ) {
        Row(Modifier.height(IntrinsicSize.Min)) {
            Box(Modifier.width(3.dp).fillMaxHeight().background(LagarTheme.layers.accent(key)))
            Column(
                modifier = Modifier.weight(1f).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
                verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
                content = content,
            )
            Icon(
                painterResource(Res.drawable.ic_chevron_right),
                contentDescription = null,
                tint = LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.align(Alignment.CenterVertically).padding(end = LagarTheme.spacing.sm),
            )
        }
    }
}

@Composable
private fun RemoveButton(icon: Painter, tint: Color, description: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = tint)
    }
}

// The filter pills use the SFS act blue, the app's primary hue; Sparade has no level of its own.
private val FILTER_LAYER = LayerKey.SfsAct
private const val EXCERPT_LINES = 3
private const val NOTE_PREVIEW_LINES = 2
private const val NOTE_LINES = 4
