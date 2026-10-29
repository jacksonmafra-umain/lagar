package app.lagar.settings

import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

/**
 * Stored lists ignore keys they do not know, so data written by a newer version still loads; fields added later
 * carry defaults, so data written by an older version loads too.
 */
internal val StoreJson = Json { ignoreUnknownKeys = true }

/** An item taken out of a saved list at [index], kept so an undo can put it back where it was. */
data class Removed<T>(val item: T, val index: Int)

/** One device-local list, stored under [key] as one JSON string; unreadable data loads as an empty list. */
internal class StoredList<T>(private val settings: Settings, private val key: String, serializer: KSerializer<T>) {
    private val serializer = ListSerializer(serializer)
    private val state = MutableStateFlow(load())

    val items: StateFlow<List<T>> = state.asStateFlow()

    val value: List<T> get() = state.value

    fun set(next: List<T>) {
        settings.putString(key, StoreJson.encodeToString(serializer, next))
        state.value = next
    }

    /** Removes the first item matching [predicate]; returns it with its position, or null when none matches. */
    fun remove(predicate: (T) -> Boolean): Removed<T>? {
        val index = value.indexOfFirst(predicate)
        if (index < 0) return null
        val item = value[index]
        set(value.filterIndexed { i, _ -> i != index })
        return Removed(item, index)
    }

    /** Puts [removed] back at its old position (clamped to the list), unless an item matching [same] is there already. */
    fun restore(removed: Removed<T>, same: (T) -> Boolean) {
        if (value.any(same)) return
        set(value.toMutableList().apply { add(removed.index.coerceIn(0, size), removed.item) })
    }

    private fun load(): List<T> {
        val stored = settings.getStringOrNull(key) ?: return emptyList()
        return try {
            StoreJson.decodeFromString(serializer, stored)
        } catch (_: SerializationException) {
            emptyList()
        } catch (_: IllegalArgumentException) {
            emptyList()
        }
    }
}
