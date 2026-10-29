package app.lagar.domain

/**
 * Query and index tokens, the same rules as the API's search index (`api/searchindex.py`, docs/api.md
 * "Text normalisation and tokens"): [normalize], then split with `[a-z]*\d{4}:\d+|[^\W_]+`, then drop
 * single letters and [STOP_WORDS]. Keep the two in sync; a shared fixture tests both.
 */
internal val STOP_WORDS: Set<String> = setOf(
    "att", "av", "de", "dem", "den", "denna", "deras", "dess", "dessa", "det", "detta", "din", "du", "eller", "en",
    "ett", "for", "fran", "har", "hon", "i", "jag", "man", "med", "mot", "nar", "och", "om", "pa", "sa", "sig", "sin",
    "ska", "skall", "som", "till", "under", "var", "vara", "vi", "vid",
)

/** Index terms of [text], in order of appearance. */
fun tokenize(text: String): List<String> {
    val folded = normalize(text)
    return tokenRanges(folded).map { folded.substring(it) }.filter { it.isIndexTerm() }
}

/** One term of a query; a [prefix] term matches every indexed term that starts with [text]. */
data class QueryTerm(val text: String, val prefix: Boolean = false)

/**
 * The terms of a type-ahead query. The last word is a prefix while the user is still typing it (the text does
 * not end in a separator) and it has at least two characters, so its matches all sit in one shard. A stop word
 * being typed is kept as a prefix only when it is the whole query ("för" may become "förordning"); after other
 * words it is dropped, so "lag om" still finds the laws.
 */
fun queryTerms(text: String): List<QueryTerm> {
    val folded = normalize(text)
    val ranges = tokenRanges(folded)
    return ranges.mapIndexedNotNull { i, range ->
        val term = folded.substring(range)
        val typing = i == ranges.lastIndex && range.last == folded.lastIndex && term.length >= 2
        when {
            typing && term in STOP_WORDS -> if (ranges.size == 1) QueryTerm(term, prefix = true) else null
            typing -> QueryTerm(term, prefix = true)
            term.isIndexTerm() -> QueryTerm(term)
            else -> null
        }
    }
}

/** First two characters of a term, anything outside `a-z` and `0-9` replaced by `_`: the shard it lives in. */
fun shardKey(term: String): String = buildString {
    for (c in term.take(2)) append(if (c in 'a'..'z' || c in '0'..'9') c else '_')
}

private fun String.isIndexTerm(): Boolean = this !in STOP_WORDS && (length > 1 || this[0].isDigit())

/**
 * Character ranges of the tokens of an already normalised [s]: at each position an SFS-style number
 * (`[a-z]*\d{4}:\d+`) wins, otherwise a run of letters and digits; anything else is skipped.
 */
internal fun tokenRanges(s: String): List<IntRange> {
    val out = mutableListOf<IntRange>()
    var i = 0
    while (i < s.length) {
        val end = sfsNumberEnd(s, i) ?: wordEnd(s, i)
        if (end > i) {
            out += i until end
            i = end
        } else {
            i++
        }
    }
    return out
}

/** End (exclusive) of `[a-z]*\d{4}:\d+` starting at [start], or null when it does not match there. */
private fun sfsNumberEnd(s: String, start: Int): Int? {
    var j = start
    while (j < s.length && s[j] in 'a'..'z') j++
    repeat(SFS_YEAR_DIGITS) {
        if (j >= s.length || !s[j].isDigit()) return null
        j++
    }
    if (j >= s.length || s[j] != ':') return null
    j++
    if (j >= s.length || !s[j].isDigit()) return null
    while (j < s.length && s[j].isDigit()) j++
    return j
}

/** End (exclusive) of the run of word characters (letters and digits, not `_`) starting at [start]. */
private fun wordEnd(s: String, start: Int): Int {
    var j = start
    while (j < s.length && s[j].isWordChar()) j++
    return j
}

/** Python's `[^\W_]`: letters and every kind of number character. */
private fun Char.isWordChar(): Boolean = isLetter() ||
    category == CharCategory.DECIMAL_DIGIT_NUMBER ||
    category == CharCategory.LETTER_NUMBER ||
    category == CharCategory.OTHER_NUMBER

private const val SFS_YEAR_DIGITS = 4
