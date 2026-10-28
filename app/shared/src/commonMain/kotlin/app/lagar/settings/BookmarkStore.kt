package app.lagar.settings

import app.lagar.data.DocumentMeta
import app.lagar.data.ListingItem
import app.lagar.domain.DisplayLayer
import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

/** A saved document. [issued] and [repealed] are null in bookmarks stored before they were kept. */
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

/** Device-local bookmarks, newest first, stored as one JSON string. */
class BookmarkStore(private val settings: Settings) {
    private val serializer = ListSerializer(Bookmark.serializer())
    private val _bookmarks = MutableStateFlow(load())

    val bookmarks: StateFlow<List<Bookmark>> = _bookmarks.asStateFlow()

    fun isBookmarked(id: String): Boolean = _bookmarks.value.any { it.id == id }

    fun toggle(b: Bookmark) {
        val current = _bookmarks.value
        val next = if (current.any { it.id == b.id }) current.filterNot { it.id == b.id } else listOf(b) + current
        save(next)
    }

    /** Replaces the stored copy of [b] with fresher data, keeping its position; does nothing if [b] is not saved. */
    fun refresh(b: Bookmark) {
        val current = _bookmarks.value
        if (current.none { it.id == b.id && it != b }) return
        save(current.map { if (it.id == b.id) b else it })
    }

    private fun save(next: List<Bookmark>) {
        settings.putString(KEY, Json.encodeToString(serializer, next))
        _bookmarks.value = next
    }

    private fun load(): List<Bookmark> {
        val stored = settings.getStringOrNull(KEY) ?: return emptyList()
        return try {
            Json.decodeFromString(serializer, stored)
        } catch (_: kotlinx.serialization.SerializationException) {
            emptyList()
        }
    }

    private companion object {
        const val KEY = "bookmarks"
    }
}
