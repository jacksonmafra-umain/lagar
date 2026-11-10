package app.lagar.speech

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class SpokenTextTest {
    @Test
    fun markdownMarksAreDropped() {
        assertEquals(
            "5 kap. Äktenskapsskillnad",
            spokenText("## 5 kap. Äktenskapsskillnad"),
        )
        assertEquals("1 § Är makarna ense, har de rätt till det.", spokenText("**1 §** Är makarna *ense*, har de rätt till det."))
    }

    @Test
    fun linksKeepTheirTextOnly() {
        assertEquals("Se lagen (1962:700) om brott.", spokenText("Se [lagen (1962:700)](https://example.org/x) om brott."))
    }

    @Test
    fun listsAndLineBreaksBecomeSentences() {
        assertEquals("Följande gäller: 1. det första, 2. det andra.", spokenText("Följande gäller:\n\n1. det första,\n2. det andra."))
    }

    @Test
    fun paragraphAndChapterSignsAreSpokenAsWords() {
        assertEquals("3 paragrafen", spokenWords("3 §"))
        assertEquals("12 kapitlet 3 paragrafen jordabalken", spokenWords("12 kap. 3 § jordabalken"))
        assertEquals("3 a paragrafen", spokenWords("3 a §"))
        assertEquals("paragraferna 2 och 3", spokenWords("§§ 2 och 3"))
    }

    @Test
    fun longTextIsSplitIntoSentencesUnderTheLimit() {
        val text = List(20) { "Detta är en mening som upprepas." }.joinToString(" ")
        val chunks = speechChunks(text, maxLength = 100)
        assertTrue(chunks.size > 1)
        chunks.forEach { assertTrue(it.length <= 100, "chunk too long: ${it.length}") }
        chunks.forEach { assertTrue(it.endsWith("."), "chunk ends mid-sentence: $it") }
        assertEquals(text, chunks.joinToString(" "))
    }

    @Test
    fun aSentenceLongerThanTheLimitIsCutAtAComma() {
        val chunks = speechChunks("a".repeat(60) + ", " + "b".repeat(60) + ".", maxLength = 80)
        assertEquals(listOf("a".repeat(60) + ",", "b".repeat(60) + "."), chunks)
    }

    @Test
    fun emptyTextHasNoChunks() {
        assertEquals(emptyList(), speechChunks("   "))
    }
}
