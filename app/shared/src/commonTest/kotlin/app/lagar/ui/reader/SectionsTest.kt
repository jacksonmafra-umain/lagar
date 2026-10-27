package app.lagar.ui.reader

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SectionsTest {
    private val excerpt = """
        # Regeringsformen

        ## 1 kap. Statsskickets grunder

        **1 §** All offentlig makt i Sverige utgår från folket.

        ## 2 kap. Grundläggande fri- och rättigheter

        **1 §** Varje medborgare är gentemot det allmänna tillförsäkrad yttrandefrihet.

        ## 3 kap. Riksdagen

        **1 §** Riksdagen är folkets främsta företrädare.
    """.trimIndent()

    @Test
    fun oneSectionPerChapter() {
        val sections = splitSections(excerpt)
        assertEquals(3, sections.size)
        assertTrue(sections[0].startsWith("# Regeringsformen"))
        assertTrue("## 1 kap. Statsskickets grunder" in sections[0])
        assertTrue(sections[1].startsWith("## 2 kap."))
        assertTrue(sections[2].startsWith("## 3 kap."))
    }

    @Test
    fun noContentIsLostOrDuplicated() {
        assertEquals(excerpt, splitSections(excerpt).joinToString("\n"))
    }

    @Test
    fun bodyWithoutChaptersIsOneSection() {
        val body = "# Lag om något\n\n**1 §** Text.\n\nMer text.\n\n### Rubrik"
        assertEquals(listOf(body), splitSections(body))
    }

    @Test
    fun emptyBodyHasNoSections() {
        assertEquals(emptyList(), splitSections(""))
    }

    @Test
    fun chapterHeadingFirstStartsTheFirstSection() {
        val sections = splitSections("## 1 kap. A\n\ntext\n\n## 2 kap. B\n\ntext")
        assertEquals(2, sections.size)
        assertTrue(sections[0].startsWith("## 1 kap. A"))
    }
}

class WithoutTitleTest {
    @Test
    fun dropsLeadingTitleLine() {
        assertEquals("## 1 kap. A\n\ntext", withoutTitle("# Lag\n\n## 1 kap. A\n\ntext"))
    }

    @Test
    fun leavesOtherSectionsAlone() {
        assertEquals("## 2 kap. B\n\ntext", withoutTitle("## 2 kap. B\n\ntext"))
    }

    @Test
    fun titleOnlyBecomesEmpty() {
        assertEquals("", withoutTitle("# Lag"))
    }
}
