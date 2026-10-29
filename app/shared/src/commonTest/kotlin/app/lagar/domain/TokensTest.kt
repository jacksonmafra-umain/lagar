package app.lagar.domain

import kotlin.test.Test
import kotlin.test.assertEquals

class TokensTest {
    @Test
    fun sfsNumbersStayWhole() {
        assertEquals(listOf("lag", "1962:700", "andring"), tokenize("Lag (1962:700) om ändring"))
        assertEquals(listOf("n2026:1"), tokenize("N2026:1"))
    }

    @Test
    fun stopWordsAndSingleLettersAreDroppedButSingleDigitsStay() {
        assertEquals(listOf("lagen", "5", "sverige"), tokenize("Lagen om att x och 5 § i Sverige"))
    }

    @Test
    fun theWordBeingTypedIsAPrefix() {
        assertEquals(listOf(QueryTerm("skol"), QueryTerm("forord", prefix = true)), queryTerms("Skol förord"))
        assertEquals(listOf(QueryTerm("skol"), QueryTerm("forord")), queryTerms("skol förord "))
    }

    @Test
    fun aStopWordBeingTypedIsKeptAsAPrefix() {
        assertEquals(listOf(QueryTerm("for", prefix = true)), queryTerms("för"))
        assertEquals(emptyList(), queryTerms("för "))
        assertEquals(listOf(QueryTerm("lag")), queryTerms("lag om"))
    }

    @Test
    fun oneCharacterIsNeverAPrefix() {
        assertEquals(listOf(QueryTerm("lag"), QueryTerm("5")), queryTerms("lag 5"))
        assertEquals(listOf(QueryTerm("lag")), queryTerms("lag s"))
    }

    @Test
    fun shardKeyIsTheFirstTwoCharactersWithOthersReplaced() {
        assertEquals("sk", shardKey("skollag"))
        assertEquals("19", shardKey("1962:700"))
        assertEquals("_b", shardKey("über"))
        assertEquals("5", shardKey("5"))
    }

    @Test
    fun tokenRangesPointIntoTheText() {
        val s = "lag (2010:800), x"
        assertEquals(listOf("lag", "2010:800", "x"), tokenRanges(s).map { s.substring(it) })
    }
}
