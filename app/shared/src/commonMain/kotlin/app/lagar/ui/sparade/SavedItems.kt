package app.lagar.ui.sparade

import app.lagar.domain.DisplayLayer
import app.lagar.settings.Bookmark
import app.lagar.settings.Note
import app.lagar.settings.SavedProvision
import app.lagar.settings.SavedService

/** What Sparade lists: everything, or one kind of saved item. */
enum class SavedFilter { All, Documents, Provisions, Notes, Services }

/** One row in Sparade. A document or provision carries the note written on it, if any. */
sealed interface SavedEntry {
    /** Unique within the list, for lazy keys. */
    val key: String

    /** The level the entry is grouped under; null for documents of a type the app does not place. */
    val layer: DisplayLayer?

    /** An entry about a document: the document itself, one of its provisions or a note on it. */
    sealed interface OnDocument : SavedEntry {
        val document: Bookmark
        override val layer: DisplayLayer? get() = document.displayLayer
    }

    data class Document(override val document: Bookmark, val note: Note?) : OnDocument {
        override val key: String get() = "d:${document.id}"
    }

    data class Provision(val provision: SavedProvision, val note: Note?) : OnDocument {
        override val document: Bookmark get() = provision.document
        override val key: String get() = "p:${document.id}#${provision.anchor}"
    }

    /** A note listed on its own: in the notes filter, or when what it is written on is not saved. */
    data class NoteOnly(val note: Note) : OnDocument {
        override val document: Bookmark get() = note.document
        override val key: String get() = "n:${document.id}#${note.anchor.orEmpty()}"
    }

    /** A saved public service, listed at the service level. */
    data class Service(val service: SavedService) : SavedEntry {
        override val key: String get() = "s:${service.id}"
        override val layer: DisplayLayer get() = DisplayLayer.Service
    }
}

/** The entries of one level; [layer] is null for documents of a type the app does not place. */
data class SavedGroup(val layer: DisplayLayer?, val entries: List<SavedEntry>)

/**
 * Sparade's list: the saved items that pass [filter] and [query], grouped by level in hierarchy order (unplaced
 * types last). Within a group, documents come first, then provisions, then notes, each newest first; the saved
 * [services] make up the service level, newest first.
 *
 * With [SavedFilter.All] a note on a saved document or provision is shown on that entry and not again on its own.
 * [query] matches, ignoring case, the document number and title, a provision's label and excerpt, note text, and a
 * service's title and issuer.
 */
fun savedGroups(
    bookmarks: List<Bookmark>,
    provisions: List<SavedProvision>,
    notes: List<Note>,
    filter: SavedFilter = SavedFilter.All,
    query: String = "",
    services: List<SavedService> = emptyList(),
): List<SavedGroup> {
    fun noteOn(id: String, anchor: String?) = notes.firstOrNull { it.isAt(id, anchor) }
    val entries = buildList {
        if (filter == SavedFilter.All || filter == SavedFilter.Documents) {
            bookmarks.forEach { add(SavedEntry.Document(it, noteOn(it.id, null))) }
        }
        if (filter == SavedFilter.All || filter == SavedFilter.Provisions) {
            provisions.forEach { add(SavedEntry.Provision(it, noteOn(it.document.id, it.anchor))) }
        }
        when (filter) {
            SavedFilter.Notes -> notes.forEach { add(SavedEntry.NoteOnly(it)) }
            SavedFilter.All -> notes.filterNot { note ->
                if (note.anchor == null) {
                    bookmarks.any { it.id == note.document.id }
                } else {
                    provisions.any { it.isAt(note.document.id, note.anchor) }
                }
            }.forEach { add(SavedEntry.NoteOnly(it)) }
            else -> Unit
        }
        if (filter == SavedFilter.All || filter == SavedFilter.Services) {
            services.forEach { add(SavedEntry.Service(it)) }
        }
    }
    val needle = query.trim().lowercase()
    val matching = if (needle.isEmpty()) entries else entries.filter { needle in it.searchText() }
    return matching
        .groupBy { it.layer }
        .entries
        .sortedBy { it.key?.ordinal ?: Int.MAX_VALUE }
        .map { SavedGroup(it.key, it.value) }
}

private fun SavedEntry.searchText(): String {
    val parts = when (this) {
        is SavedEntry.Service -> mutableListOf(service.title, service.issuer)
        is SavedEntry.OnDocument -> mutableListOf(document.number, document.title)
    }
    when (this) {
        is SavedEntry.Document -> note?.let { parts += it.text }
        is SavedEntry.Provision -> {
            parts += provision.label
            parts += provision.excerpt
            note?.let { parts += it.text }
        }
        is SavedEntry.NoteOnly -> {
            note.label?.let { parts += it }
            parts += note.text
        }
        is SavedEntry.Service -> Unit
    }
    return parts.joinToString("\n").lowercase()
}
