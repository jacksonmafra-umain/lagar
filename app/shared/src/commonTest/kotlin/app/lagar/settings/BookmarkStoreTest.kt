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

    private fun provision(id: String, anchor: String) = SavedProvision(bookmark(id), anchor, "${anchor.drop(1)} §", "Text of $anchor")

    @Test
    fun provisionToggleAddsThenRemovesNewestFirst() {
        val store = BookmarkStore(MapSettings())
        store.toggleProvision(provision("1", "p1"))
        store.toggleProvision(provision("1", "p2"))
        assertTrue(store.isProvisionSaved("1", "p1"))
        assertEquals(listOf("p2", "p1"), store.provisions.value.map { it.anchor })
        store.toggleProvision(provision("1", "p1"))
        assertFalse(store.isProvisionSaved("1", "p1"))
        assertEquals(listOf("p2"), store.provisions.value.map { it.anchor })
    }

    @Test
    fun provisionsAreKeptApartFromDocuments() {
        val settings = MapSettings()
        val store = BookmarkStore(settings)
        store.toggleProvision(provision("1", "k3p1"))
        assertFalse(store.isBookmarked("1"))
        assertTrue(store.bookmarks.value.isEmpty())
        assertEquals(listOf(provision("1", "k3p1")), BookmarkStore(settings).provisions.value)
    }

    @Test
    fun provisionsPersistWithTheirDocument() {
        val settings = MapSettings()
        val saved = SavedProvision(bookmark("1").copy(issued = "1962-12-21", repealed = "2020-01-01"), "k3p1", "3 kap. 1 §", "Den som")
        BookmarkStore(settings).toggleProvision(saved)
        assertEquals(listOf(saved), BookmarkStore(settings).provisions.value)
    }

    @Test
    fun provisionsWithoutDatesOrExcerptLoad() {
        val settings = MapSettings()
        settings.putString(
            "saved_provisions",
            """[{"document":{"id":"1","title":"Title 1","number":"2020:1","type":"act","layer":"sfs"},"anchor":"p1","label":"1 §"}]""",
        )
        val loaded = BookmarkStore(settings).provisions.value.single()
        assertEquals(SavedProvision(bookmark("1"), "p1", "1 §"), loaded)
        assertNull(loaded.document.issued)
        assertEquals("", loaded.excerpt)
    }

    @Test
    fun unknownStoredKeysAreIgnored() {
        val settings = MapSettings()
        settings.putString("bookmarks", """[{"id":"1","title":"Title 1","number":"2020:1","type":"act","layer":"sfs","pinned":true}]""")
        assertEquals(listOf(bookmark("1")), BookmarkStore(settings).bookmarks.value)
    }

    @Test
    fun unreadableDataLoadsEmpty() {
        val settings = MapSettings()
        settings.putString("bookmarks", "not json")
        settings.putString("saved_provisions", """{"anchor":1}""")
        val store = BookmarkStore(settings)
        assertTrue(store.bookmarks.value.isEmpty())
        assertTrue(store.provisions.value.isEmpty())
    }

    @Test
    fun removeThenRestorePutsTheBookmarkBackInPlace() {
        val settings = MapSettings()
        val store = BookmarkStore(settings)
        listOf("1", "2", "3").forEach { store.toggle(bookmark(it)) }
        val removed = store.remove("2")!!
        assertEquals(1, removed.index)
        assertEquals(listOf("3", "1"), store.bookmarks.value.map { it.id })
        store.restore(removed)
        assertEquals(listOf("3", "2", "1"), store.bookmarks.value.map { it.id })
        assertEquals(listOf("3", "2", "1"), BookmarkStore(settings).bookmarks.value.map { it.id })
    }

    @Test
    fun restoreDoesNotDuplicate() {
        val store = BookmarkStore(MapSettings())
        store.toggle(bookmark("1"))
        val removed = store.remove("1")!!
        store.toggle(bookmark("1"))
        store.restore(removed)
        assertEquals(listOf("1"), store.bookmarks.value.map { it.id })
        assertNull(store.remove("missing"))
    }

    @Test
    fun removeThenRestoreProvision() {
        val store = BookmarkStore(MapSettings())
        store.toggleProvision(provision("1", "p1"))
        store.toggleProvision(provision("1", "p2"))
        val removed = store.removeProvision("1", "p1")!!
        assertEquals(listOf("p2"), store.provisions.value.map { it.anchor })
        store.restoreProvision(removed)
        assertEquals(listOf("p2", "p1"), store.provisions.value.map { it.anchor })
    }

    @Test
    fun refreshUpdatesTheProvisionSnapshots() {
        val settings = MapSettings()
        val store = BookmarkStore(settings)
        store.toggleProvision(provision("1", "p1"))
        store.toggleProvision(provision("2", "p1"))
        val fresh = bookmark("1").copy(repealed = "2024-07-01")
        store.refresh(fresh)
        assertEquals(listOf(bookmark("2"), fresh), store.provisions.value.map { it.document })
        assertTrue(store.bookmarks.value.isEmpty())
        assertEquals(fresh, BookmarkStore(settings).provisions.value.last().document)
    }
}
