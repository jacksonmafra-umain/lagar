package app.lagar.settings

import app.lagar.domain.DisplayLayer
import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

@Serializable
data class Bookmark(val id: String, val title: String, val number: String, val type: String, val layer: String) {
    /** The display level, picked from [type] so acts and ordinances get their own colors. */
    val displayLayer: DisplayLayer? get() = DisplayLayer.fromRoute(layer, type)
}

/** Device-local bookmarks, newest first, stored as one JSON string. */
class BookmarkStore(private val settings: Settings) {
    private val serializer = ListSerializer(Bookmark.serializer())
    private val _bookmarks = MutableStateFlow(load())

    val bookmarks: StateFlow<List<Bookmark>> = _bookmarks.asStateFlow()

    fun isBookmarked(id: String): Boolean = _bookmarks.value.any { it.id == id }

    fun toggle(b: Bookmark) {
        val current = _bookmarks.value
        val next = if (current.any { it.id == b.id }) current.filterNot { it.id == b.id } else listOf(b) + current
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
