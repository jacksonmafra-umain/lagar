package app.lagar.settings

import com.russhwolf.settings.MapSettings
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class NoteStoreTest {
    private val doc = Bookmark("sfs-1962-700", "Brottsbalk (1962:700)", "1962:700", "act", "sfs")

    @Test
    fun writesAndReadsDocumentAndProvisionNotes() {
        val store = NoteStore(MapSettings())
        store.write(doc, null, null, "Read before the exam")
        store.write(doc, "k3p1", "3 kap. 1 §", "Murder")
        assertEquals("Read before the exam", store.noteAt(doc.id, null)?.text)
        assertEquals(Note(doc, "Murder", "k3p1", "3 kap. 1 §"), store.noteAt(doc.id, "k3p1"))
        assertNull(store.noteAt(doc.id, "k3p2"))
        assertEquals(listOf("k3p1", null), store.notes.value.map { it.anchor })
    }

    @Test
    fun editKeepsThePlaceAndTrims() {
        val store = NoteStore(MapSettings())
        store.write(doc, "p1", "1 §", "one")
        store.write(doc, "p2", "2 §", "two")
        store.write(doc, "p1", "1 §", "  one, edited \n")
        assertEquals(listOf("two", "one, edited"), store.notes.value.map { it.text })
    }

    @Test
    fun blankTextDeletes() {
        val store = NoteStore(MapSettings())
        store.write(doc, "p1", "1 §", "one")
        store.write(doc, "p1", "1 §", "   ")
        assertTrue(store.notes.value.isEmpty())
    }

    @Test
    fun persistsAcrossInstances() {
        val settings = MapSettings()
        NoteStore(settings).write(doc, "p1", "1 §", "one")
        assertEquals(listOf(Note(doc, "one", "p1", "1 §")), NoteStore(settings).notes.value)
    }

    @Test
    fun documentNotesStoreNoAnchor() {
        val settings = MapSettings()
        NoteStore(settings).write(doc, null, null, "one")
        assertTrue("anchor" !in settings.getString("notes", ""))
    }

    @Test
    fun deleteThenRestore() {
        val store = NoteStore(MapSettings())
        store.write(doc, "p1", "1 §", "one")
        store.write(doc, "p2", "2 §", "two")
        val removed = store.delete(doc.id, "p1")!!
        assertEquals(listOf("p2"), store.notes.value.map { it.anchor })
        store.restore(removed)
        assertEquals(listOf("p2", "p1"), store.notes.value.map { it.anchor })
        assertNull(store.delete(doc.id, "missing"))
    }

    @Test
    fun oldDocumentSnapshotsLoad() {
        val settings = MapSettings()
        settings.putString(
            "notes",
            """[{"document":{"id":"1","title":"T","number":"2020:1","type":"act","layer":"sfs"},"text":"hi"}]""",
        )
        val note = NoteStore(settings).notes.value.single()
        assertEquals(Note(Bookmark("1", "T", "2020:1", "act", "sfs"), "hi"), note)
    }

    @Test
    fun refreshUpdatesTheSnapshot() {
        val store = NoteStore(MapSettings())
        store.write(doc, null, null, "one")
        val fresh = doc.copy(repealed = "2030-01-01")
        store.refresh(fresh)
        assertEquals(fresh, store.notes.value.single().document)
    }
}
