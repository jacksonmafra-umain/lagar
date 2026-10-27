package app.lagar.settings

import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class BookmarkStoreTest {
    private fun bookmark(id: String) = Bookmark(id, "Title $id", "2020:$id", "act", "sfs")

    @Test
    fun toggleAddsThenRemoves() {
        val store = BookmarkStore(MapSettings())
        store.toggle(bookmark("1"))
        assertTrue(store.isBookmarked("1"))
        store.toggle(bookmark("1"))
        assertFalse(store.isBookmarked("1"))
        assertTrue(store.bookmarks.value.isEmpty())
    }

    @Test
    fun persistsAcrossInstances() {
        val settings = MapSettings()
        BookmarkStore(settings).toggle(bookmark("1"))
        assertEquals(listOf(bookmark("1")), BookmarkStore(settings).bookmarks.value)
    }

    @Test
    fun newestFirst() {
        val store = BookmarkStore(MapSettings())
        store.toggle(bookmark("1"))
        store.toggle(bookmark("2"))
        assertEquals(listOf("2", "1"), store.bookmarks.value.map { it.id })
    }
}
