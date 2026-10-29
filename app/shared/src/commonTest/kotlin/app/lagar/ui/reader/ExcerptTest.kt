package app.lagar.ui.reader

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ExcerptTest {
    @Test
    fun dropsTheStatuteNumberAndMarkup() {
        assertEquals(
            "Den som berövar annan livet, döms för mord.",
            provisionExcerpt("**1 §** Den som berövar annan livet,\ndöms för *mord*."),
        )
        assertEquals("Text", provisionExcerpt("**3 a §** Text"))
        assertEquals("Text", provisionExcerpt("**4 §§** Text"))
    }

    @Test
    fun aChapterKeepsItsHeading() {
        assertEquals("3 kap. Om brott mot liv och hälsa", provisionExcerpt("## 3 kap. Om brott mot liv och hälsa"))
    }

    @Test
    fun cutsAtAWordWithAnEllipsis() {
        val excerpt = provisionExcerpt("**1 §** alpha beta gamma delta, epsilon", max = 30)
        assertEquals("alpha beta gamma delta…", excerpt)
        assertTrue(excerpt.length <= 31)
    }

    @Test
    fun notePreviewIsOneLine() {
        assertEquals("first second", notePreview("first\n\n  second"))
    }
}
