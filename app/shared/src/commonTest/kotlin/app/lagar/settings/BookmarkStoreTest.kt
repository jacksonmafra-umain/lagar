package app.lagar.settings

import app.lagar.data.DocumentMeta
import app.lagar.data.ListingItem
import app.lagar.domain.DisplayLayer
import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
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

    @Test
    fun displayLayerFollowsTheType() {
        assertEquals(DisplayLayer.SfsAct, bookmark("1").displayLayer)
        assertEquals(DisplayLayer.SfsOrdinance, Bookmark("2", "T", "1999:175", "ordinance", "sfs").displayLayer)
        assertEquals(DisplayLayer.Fundamental, Bookmark("3", "T", "1974:152", "fundamental_law", "fundamental").displayLayer)
        assertNull(Bookmark("4", "T", "1", "bylaw", "sfs").displayLayer)
    }

    @Test
    fun displayLayerIsNotStored() {
        val settings = MapSettings()
        BookmarkStore(settings).toggle(bookmark("1"))
        assertFalse(settings.getString("bookmarks", "").contains("displayLayer"))
    }

    @Test
    fun storesIssuedAndRepealed() {
        val settings = MapSettings()
        val repealed = bookmark("1").copy(issued = "1999-03-25", repealed = "2005-01-01")
        BookmarkStore(settings).toggle(repealed)
        assertEquals(listOf(repealed), BookmarkStore(settings).bookmarks.value)
    }

    @Test
    fun oldBookmarksLoadWithoutDates() {
        val settings = MapSettings()
        settings.putString("bookmarks", """[{"id":"1","title":"Title 1","number":"2020:1","type":"act","layer":"sfs"}]""")
        val loaded = BookmarkStore(settings).bookmarks.value.single()
        assertEquals(bookmark("1"), loaded)
        assertNull(loaded.issued)
        assertNull(loaded.repealed)
    }

    @Test
    fun refreshUpdatesInPlaceAndPersists() {
        val settings = MapSettings()
        val store = BookmarkStore(settings)
        store.toggle(bookmark("1"))
        store.toggle(bookmark("2"))
        val fresh = bookmark("1").copy(issued = "2020-01-01", repealed = "2024-07-01")
        store.refresh(fresh)
        assertEquals(listOf(bookmark("2"), fresh), store.bookmarks.value)
        assertEquals(listOf(bookmark("2"), fresh), BookmarkStore(settings).bookmarks.value)
    }

    @Test
    fun refreshIgnoresDocumentsThatAreNotSaved() {
        val store = BookmarkStore(MapSettings())
        store.refresh(bookmark("1"))
        assertTrue(store.bookmarks.value.isEmpty())
    }

    @Test
    fun repealedSurvivesTheMappings() {
        val meta = DocumentMeta(
            "sfs-1999-100", "Exempelförordning (1999:100)", "ordinance", "sfs", "1999:100", "1999-03-25", null, "2005-01-01",
            emptyList(), null, emptyList(), null, null, "sv", false, "https://example.org", "", "",
        )
        val saved = meta.toBookmark()
        assertEquals(Bookmark("sfs-1999-100", "Exempelförordning (1999:100)", "1999:100", "ordinance", "sfs", "1999-03-25", "2005-01-01"), saved)
        assertEquals(
            ListingItem("sfs-1999-100", "Exempelförordning (1999:100)", "1999:100", "ordinance", "1999-03-25", "2005-01-01"),
            saved.toListingItem(),
        )
    }
}
