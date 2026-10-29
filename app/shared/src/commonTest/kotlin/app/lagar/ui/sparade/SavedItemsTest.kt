package app.lagar.ui.sparade

import app.lagar.domain.DisplayLayer
import app.lagar.settings.Bookmark
import app.lagar.settings.Note
import app.lagar.settings.SavedProvision
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SavedItemsTest {
    private val act = Bookmark("sfs-1962-700", "Brottsbalk (1962:700)", "1962:700", "act", "sfs")
    private val ordinance = Bookmark("sfs-1999-175", "Rättsinformationsförordning (1999:175)", "1999:175", "ordinance", "sfs")
    private val constitution = Bookmark("sfs-1974-152", "Regeringsform (1974:152)", "1974:152", "fundamental_law", "fundamental")
    private val unplaced = Bookmark("x-1", "Stadga", "1", "bylaw", "sfs")
    private val murder = SavedProvision(act, "k3p1", "3 kap. 1 §", "Den som berövar annan livet")
    private val theft = SavedProvision(act, "k8p1", "8 kap. 1 §", "Den som olovligen tager")

    @Test
    fun groupsByLevelInHierarchyOrder() {
        val groups = savedGroups(listOf(unplaced, ordinance, act, constitution), emptyList(), emptyList())
        assertEquals(listOf(DisplayLayer.Fundamental, DisplayLayer.SfsAct, DisplayLayer.SfsOrdinance, null), groups.map { it.layer })
    }

    @Test
    fun documentsThenProvisionsThenNotesWithinAGroup() {
        val loose = Note(act, "Loose note", "k5p1", "5 kap. 1 §")
        val groups = savedGroups(listOf(act), listOf(theft, murder), listOf(loose))
        assertEquals(listOf("d:sfs-1962-700", "p:sfs-1962-700#k8p1", "p:sfs-1962-700#k3p1", "n:sfs-1962-700#k5p1"), groups.single().entries.map { it.key })
    }

    @Test
    fun notesOnSavedItemsAreShownOnThemInAll() {
        val docNote = Note(act, "Exam")
        val murderNote = Note(act, "Compare 3 kap. 2 §", "k3p1", "3 kap. 1 §")
        val entries = savedGroups(listOf(act), listOf(murder), listOf(murderNote, docNote)).single().entries
        assertEquals(2, entries.size)
        assertEquals(docNote, (entries[0] as SavedEntry.Document).note)
        assertEquals(murderNote, (entries[1] as SavedEntry.Provision).note)
    }

    @Test
    fun notesOnUnsavedItemsAreListedOnTheirOwn() {
        val docNote = Note(ordinance, "Check")
        val entries = savedGroups(emptyList(), listOf(murder), listOf(docNote)).flatMap { it.entries }
        assertEquals(listOf("p:sfs-1962-700#k3p1", "n:sfs-1999-175#"), entries.map { it.key })
    }

    @Test
    fun filters() {
        val note = Note(act, "Exam")
        val bookmarks = listOf(act)
        val provisions = listOf(murder)
        val notes = listOf(note)
        fun keys(f: SavedFilter) = savedGroups(bookmarks, provisions, notes, f).flatMap { g -> g.entries.map { it.key } }
        assertEquals(listOf("d:sfs-1962-700"), keys(SavedFilter.Documents))
        assertEquals(listOf("p:sfs-1962-700#k3p1"), keys(SavedFilter.Provisions))
        assertEquals(listOf("n:sfs-1962-700#"), keys(SavedFilter.Notes))
        assertEquals(listOf("d:sfs-1962-700", "p:sfs-1962-700#k3p1"), keys(SavedFilter.All))
    }

    @Test
    fun searchMatchesTitlesLabelsExcerptsAndNotesIgnoringCase() {
        val note = Note(ordinance, "Fråga handledaren")
        fun keys(q: String) = savedGroups(listOf(act, constitution), listOf(murder, theft), listOf(note), query = q).flatMap { g -> g.entries.map { it.key } }
        assertEquals(listOf("d:sfs-1974-152"), keys("regeringsform"))
        assertEquals(listOf("p:sfs-1962-700#k8p1"), keys("8 KAP"))
        assertEquals(listOf("p:sfs-1962-700#k3p1"), keys("livet"))
        assertEquals(listOf("n:sfs-1999-175#"), keys("HANDLEDAREN"))
        assertEquals(listOf("d:sfs-1962-700", "p:sfs-1962-700#k3p1", "p:sfs-1962-700#k8p1"), keys(" 1962:700 "))
        assertTrue(keys("nothing like this").isEmpty())
    }

    @Test
    fun emptyGroupsAreDropped() {
        assertTrue(savedGroups(listOf(act), emptyList(), emptyList(), SavedFilter.Provisions).isEmpty())
    }
}
