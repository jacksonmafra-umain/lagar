package app.lagar.settings

import app.lagar.data.DocumentMeta
import app.lagar.data.ListingItem
import app.lagar.domain.DisplayLayer
import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.StateFlow
import kotlinx.serialization.Serializable

/**
 * A saved document, and the document snapshot kept with saved provisions and notes. [issued] and [repealed] are
 * null in bookmarks stored before they were kept.
 */
@Serializable
data class Bookmark(
    val id: String,
    val title: String,
    val number: String,
    val type: String,
    val layer: String,
    val issued: String? = null,
    val repealed: String? = null,
) {
    /** The display level, picked from [type] so acts and ordinances get their own colors. */
    val displayLayer: DisplayLayer? get() = DisplayLayer.fromRoute(layer, type)
}

fun Bookmark.toListingItem(): ListingItem = ListingItem(id, title, number, type, issued, repealed)

fun DocumentMeta.toBookmark(): Bookmark = Bookmark(id, title, number, type, layer, issued, repealed)

/**
 * One saved § or chapter: the [document] it belongs to, its outline [anchor] (`k3p1`), how the text names it
 * ([label], `3 kap. 1 §`) and the start of its text ([excerpt]).
 */
@Serializable
data class SavedProvision(
    val document: Bookmark,
    val anchor: String,
    val label: String,
    val excerpt: String = "",
) {
    fun isAt(documentId: String, anchor: String): Boolean = document.id == documentId && this.anchor == anchor
}

/**
 * Device-local saved items, newest first: whole documents ([bookmarks], stored under `bookmarks` as before) and
 * single provisions ([provisions], under `saved_provisions`).
 */
class BookmarkStore(settings: Settings) {
    private val documents = StoredList(settings, KEY, Bookmark.serializer())
    private val savedProvisions = StoredList(settings, KEY_PROVISIONS, SavedProvision.serializer())

    val bookmarks: StateFlow<List<Bookmark>> = documents.items
    val provisions: StateFlow<List<SavedProvision>> = savedProvisions.items

    fun isBookmarked(id: String): Boolean = documents.value.any { it.id == id }

    fun toggle(b: Bookmark) {
        if (remove(b.id) == null) documents.set(listOf(b) + documents.value)
    }

    /** Removes the bookmark of document [id]; the result undoes it through [restore]. */
    fun remove(id: String): Removed<Bookmark>? = documents.remove { it.id == id }

    fun restore(removed: Removed<Bookmark>) = documents.restore(removed) { it.id == removed.item.id }

    fun isProvisionSaved(documentId: String, anchor: String): Boolean = savedProvisions.value.any { it.isAt(documentId, anchor) }

    fun toggleProvision(p: SavedProvision) {
        if (removeProvision(p.document.id, p.anchor) == null) savedProvisions.set(listOf(p) + savedProvisions.value)
    }

    fun removeProvision(documentId: String, anchor: String): Removed<SavedProvision>? =
        savedProvisions.remove { it.isAt(documentId, anchor) }

    fun restoreProvision(removed: Removed<SavedProvision>) =
        savedProvisions.restore(removed) { it.isAt(removed.item.document.id, removed.item.anchor) }

    /**
     * Replaces the stored copy of document [b], and the snapshot kept with its saved provisions, with fresher data,
     * keeping positions; does nothing for a document that is not saved.
     */
    fun refresh(b: Bookmark) {
        if (documents.value.any { it.id == b.id && it != b }) {
            documents.set(documents.value.map { if (it.id == b.id) b else it })
        }
        if (savedProvisions.value.any { it.document.id == b.id && it.document != b }) {
            savedProvisions.set(savedProvisions.value.map { if (it.document.id == b.id) it.copy(document = b) else it })
        }
    }

    private companion object {
        const val KEY = "bookmarks"
        const val KEY_PROVISIONS = "saved_provisions"
    }
}
