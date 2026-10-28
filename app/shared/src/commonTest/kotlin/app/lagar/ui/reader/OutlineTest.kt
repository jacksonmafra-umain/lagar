package app.lagar.ui.reader

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class OutlineTest {
    private val body = """
        # Brottsbalk (1962:700)

        **1 §** Inledande bestämmelse.

        ## 1 kap. Om brott och brottspåföljder

        **1 §** Brott är en gärning.

        **3 §** /Upphör att gälla/ Äldre lydelse.

        **3 §** /Träder i kraft/ Ny lydelse.

        **3 a §** Tillagd paragraf.

        ## 2 a kap. Särskilda bestämmelser

        Mellanrubrik

        **4 §§** Upphävda.

        ## Övergångsbestämmelser

        Text utan paragrafer.
    """.trimIndent()

    private val blocks = readerBlocks(body)
    private val outline = buildOutline(blocks)

    @Test
    fun readerBlocksDropTheTitleAndBlankBlocks() {
        assertTrue(blocks.none { it.startsWith("# ") || it.isBlank() })
        assertTrue(blocks.first().startsWith("**1 §** Inledande"))
    }

    @Test
    fun groupsStatutesUnderTheirChapters() {
        assertEquals(listOf(null, "1 kap. Om brott och brottspåföljder", "2 a kap. Särskilda bestämmelser", "Övergångsbestämmelser"), outline.chapters.map { it.title })
        assertEquals(listOf(null, "k1", "k2a", "h1"), outline.chapters.map { it.anchor })
        assertEquals(listOf("1 §", "3 §", "3 §", "3 a §"), outline.chapters[1].statutes.map { it.label })
        assertEquals(listOf("4 §"), outline.chapters[2].statutes.map { it.label })
    }

    @Test
    fun anchorsAreUniqueAndUrlSafe() {
        val anchors = outline.chapters.flatMap { c -> listOfNotNull(c.anchor) + c.statutes.map { it.anchor } }
        assertEquals(listOf("p1", "k1", "k1p1", "k1p3", "k1p3-2", "k1p3a", "k2a", "k2ap4", "h1"), anchors)
        assertTrue(anchors.all { Regex("[a-z0-9-]+").matches(it) })
    }

    @Test
    fun anchorsPointAtTheirBlocks() {
        val index = outline.blockOf("k1p3a")!!
        assertTrue(blocks[index].startsWith("**3 a §**"))
        assertTrue(blocks[outline.blockOf("k2a")!!].startsWith("## 2 a kap."))
        assertEquals("k1p3-2", outline.anchorOf(outline.blockOf("k1p3-2")!!))
        assertNull(outline.blockOf("k9p1"))
    }

    @Test
    fun labelsNameChapterAndStatute() {
        assertEquals("1 kap. 3 a §", outline.labelOf(outline.blockOf("k1p3a")!!))
        assertEquals("2 a kap. 4 §", outline.labelOf(outline.blockOf("k2ap4")!!))
        assertEquals("1 §", outline.labelOf(outline.blockOf("p1")!!))
        assertEquals("Övergångsbestämmelser", outline.labelOf(outline.blockOf("h1")!!))
    }

    @Test
    fun documentWithoutStatutesHasAnEmptyOutline() {
        val plain = buildOutline(readerBlocks("# Titel\n\nBara text."))
        assertTrue(plain.isEmpty)
        assertNull(plain.blockOf("p1"))
    }

    @Test
    fun largeDocumentBuildsQuickly() {
        val big = buildString {
            append("# Balk\n")
            repeat(40) { k -> append("\n## ${k + 1} kap. Kapitel\n"); repeat(30) { p -> append("\n**${p + 1} §** Text.\n") } }
        }
        val large = buildOutline(readerBlocks(big))
        assertEquals(40, large.chapters.size)
        assertEquals(1200, large.chapters.sumOf { it.statutes.size })
        assertTrue(large.blockOf("k40p30") != null)
    }
}
