package app.lagar.settings

import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.StateFlow
import kotlinx.serialization.Serializable

/**
 * A private note on a [document], or on one of its provisions when [anchor] is set ([label] then names it,
 * `3 kap. 1 §`). Notes stay on the device: there are no accounts and nothing is synced.
 */
@Serializable
data class Note(
    val document: Bookmark,
    val text: String,
    val anchor: String? = null,
    val label: String? = null,
) {
    fun isAt(documentId: String, anchor: String?): Boolean = document.id == documentId && this.anchor == anchor
}

/** Device-local notes, newest first, stored under `notes` with the same mechanism as bookmarks. */
class NoteStore(settings: Settings) {
    private val stored = StoredList(settings, KEY, Note.serializer())

    val notes: StateFlow<List<Note>> = stored.items

    fun noteAt(documentId: String, anchor: String?): Note? = stored.value.firstOrNull { it.isAt(documentId, anchor) }

    /**
     * Writes the note on [document] (or on its provision at [anchor]). An edit keeps the note's place, a new note
     * goes first, and blank [text] deletes the note.
     */
    fun write(document: Bookmark, anchor: String?, label: String?, text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) {
            delete(document.id, anchor)
            return
        }
        val note = Note(document, trimmed, anchor, label)
        val current = stored.value
        stored.set(
            if (current.any { it.isAt(document.id, anchor) }) {
                current.map { if (it.isAt(document.id, anchor)) note else it }
            } else {
                listOf(note) + current
            },
        )
    }

    /** Deletes the note at [anchor] of [documentId] (the document note when null); the result undoes it through [restore]. */
    fun delete(documentId: String, anchor: String?): Removed<Note>? = stored.remove { it.isAt(documentId, anchor) }

    fun restore(removed: Removed<Note>) = stored.restore(removed) { it.isAt(removed.item.document.id, removed.item.anchor) }

    /** Updates the document snapshot kept with the notes on [b], keeping their order. */
    fun refresh(b: Bookmark) {
        if (stored.value.none { it.document.id == b.id && it.document != b }) return
        stored.set(stored.value.map { if (it.document.id == b.id) it.copy(document = b) else it })
    }

    private companion object {
        const val KEY = "notes"
    }
}
