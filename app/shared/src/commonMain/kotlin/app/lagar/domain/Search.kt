package app.lagar.domain

import app.lagar.data.ListingItem
import app.lagar.data.NewestFirst
import kotlinx.datetime.LocalDate

/** Which fields the text must match: [All] is titles and numbers, [FullText] adds the body text. */
enum class SearchMode { All, Title, Number, FullText }

enum class StatusFilter { All, InForce, Repealed }

enum class SortOrder { Relevance, Newest, Number }

/**
 * [types] matches [ListingItem.type] (empty = all); [from] and [to] bound `issued` inclusively, [inForceFrom]
 * and [inForceTo] bound `in_force`. [vacatioLegis] keeps documents whose entry into force is still ahead.
 * Documents without an `in_force` date never match an in-force filter.
 */
data class SearchQuery(
    val text: String,
    val types: Set<String> = emptySet(),
    val from: LocalDate? = null,
    val to: LocalDate? = null,
    val mode: SearchMode = SearchMode.All,
    val status: StatusFilter = StatusFilter.All,
    val inForceFrom: LocalDate? = null,
    val inForceTo: LocalDate? = null,
    val vacatioLegis: Boolean = false,
    val sort: SortOrder = SortOrder.Relevance,
) {
    val isValidRange: Boolean
        get() = (from == null || to == null || from <= to) && (inForceFrom == null || inForceTo == null || inForceFrom <= inForceTo)

    /** Whether a filter needs the `in_force` date. */
    val usesInForce: Boolean get() = inForceFrom != null || inForceTo != null || vacatioLegis

    private val hasFilter: Boolean
        get() = types.isNotEmpty() || from != null || to != null || status != StatusFilter.All || usesInForce

    internal val isActive: Boolean get() = text.isNotBlank() || hasFilter
}

/** Bits of the search index's `field_bits`. */
object SearchField {
    const val TITLE = 1
    const val NUMBER = 2
    const val BODY = 4
}

/** The field bits a match may come from in this mode. */
val SearchMode.fieldMask: Int
    get() = when (this) {
        SearchMode.All -> SearchField.TITLE or SearchField.NUMBER
        SearchMode.Title -> SearchField.TITLE
        SearchMode.Number -> SearchField.NUMBER
        SearchMode.FullText -> SearchField.TITLE or SearchField.NUMBER or SearchField.BODY
    }

/**
 * One result. [anyFields] is the OR of the fields any query term matched in, [allFields] the fields every term
 * matched in; both are 0 for a filter-only query.
 */
data class SearchHit(val item: ListingItem, val anyFields: Int = 0, val allFields: Int = 0) {
    /** Matched only in the body text, so the title shows nothing of why it was found. */
    val bodyOnly: Boolean get() = anyFields == SearchField.BODY
}

private const val ACCENTED = "åäöàáâãāăąçćčďđèéêëēėęěìíîïīįłñńňòóôõøōőŕřśšşťùúûūůűųýÿźżž"
private const val PLAIN = "aaoaaaaaaacccddeeeeeeeeiiiiiilnnnooooooorrssstuuuuuuuyyzzz"

/** Lowercases and folds diacritics, so "Åre" and "are" match; å/ä/ö become a/a/o. */
fun normalize(s: String): String = buildString(s.length) {
    for (c in s.lowercase()) append(fold(c))
}

private fun fold(c: Char): Char {
    val i = ACCENTED.indexOf(c)
    return if (i >= 0) PLAIN[i] else c
}

/** [normalize] one character at a time, so index `i` of the result is character `i` of [s]. */
internal fun normalizeAligned(s: String): String = buildString(s.length) {
    for (c in s) append(fold(c.lowercaseChar()))
}

/** Keeps input order. Blank text with no other filter matches nothing; an inverted date range too. */
fun List<ListingItem>.search(q: SearchQuery, today: LocalDate? = null): List<ListingItem> =
    searchHits(q, today).map { it.item }

/**
 * Substring search over titles and numbers, for when the API has no search index. Every term must occur in a
 * field of [SearchQuery.mode] (in a title, a term with a definite ending may occur without it, see
 * [definiteBase]); the body is not available, so [SearchMode.FullText] searches titles and numbers.
 */
fun List<ListingItem>.searchHits(q: SearchQuery, today: LocalDate? = null): List<SearchHit> {
    if (!q.isValidRange || !q.isActive) return emptyList()
    val terms = normalize(q.text).split(Regex("\\s+")).filter { it.isNotEmpty() }
    val mask = q.mode.fieldMask
    return mapNotNull { item ->
        if (!item.passes(q, today)) return@mapNotNull null
        if (terms.isEmpty()) return@mapNotNull SearchHit(item)
        val title = normalize(item.title)
        val number = normalize(item.number)
        var any = 0
        var all = mask
        for (term in terms) {
            val base = definiteBase(term)
            val inTitle = term in title || (base != null && base in title)
            val bits = ((if (inTitle) SearchField.TITLE else 0) or (if (term in number) SearchField.NUMBER else 0)) and mask
            if (bits == 0) return@mapNotNull null
            any = any or bits
            all = all and bits
        }
        SearchHit(item, any, all)
    }
}

/**
 * Whether [this] passes the non-text filters of [q]. [today] is needed only for [SearchQuery.vacatioLegis];
 * without it that filter matches nothing.
 */
fun ListingItem.passes(q: SearchQuery, today: LocalDate?): Boolean {
    if (q.types.isNotEmpty() && type !in q.types) return false
    when (q.status) {
        StatusFilter.All -> Unit
        StatusFilter.InForce -> if (repealed != null) return false
        StatusFilter.Repealed -> if (repealed == null) return false
    }
    if (!inRange(issued, q.from, q.to)) return false
    if (q.inForceFrom != null || q.inForceTo != null) {
        if (!inRange(inForce, q.inForceFrom, q.inForceTo)) return false
    }
    if (q.vacatioLegis) {
        val date = parseIso(inForce) ?: return false
        if (today == null || date <= today || repealed != null) return false
    }
    return true
}

/** True without bounds; with a bound, [iso] must be a date within it. */
private fun inRange(iso: String?, from: LocalDate?, to: LocalDate?): Boolean {
    if (from == null && to == null) return true
    val date = parseIso(iso) ?: return false
    return (from == null || date >= from) && (to == null || date <= to)
}

private fun parseIso(iso: String?): LocalDate? = iso?.let { runCatching { LocalDate.parse(it) }.getOrNull() }

/** Lowest set bit, or a value past every field when none is set. */
private fun bestField(bits: Int): Int = if (bits == 0) Int.MAX_VALUE else bits and -bits

/**
 * Relevance, after the [nameMatch] of the query text: a document where every term matched in the title comes
 * first, then number, then body; then by the best field any term matched in; then more matched fields; then newest.
 */
private val ByFields: Comparator<SearchHit> =
    compareBy<SearchHit> { bestField(it.allFields) }
        .thenBy { bestField(it.anyFields) }
        .thenByDescending { it.anyFields.countOneBits() }
        .then(compareBy(NewestFirst) { it.item })

/** How a document's name answers a query, best first: see [nameMatch]. */
internal enum class NameMatch { Exact, Start, None }

/**
 * Whether [item] is the document the query [text] names. [NameMatch.Exact]: the title, the title without its
 * trailing number ("Brottsbalk" of "Brottsbalk (1962:700)") or the number equals the text. [NameMatch.Start]:
 * the title starts with the text, the last word being typed as a prefix. Words compare accent-insensitively, and
 * a query word with a definite ending also equals its base ("miljöbalken" names "Miljöbalk (1998:808)").
 */
internal fun nameMatch(item: ListingItem, text: String): NameMatch {
    val query = words(text)
    if (query.isEmpty()) return NameMatch.None
    val title = words(item.title)
    val number = words(item.number)
    val name = if (number.isNotEmpty() && title.takeLast(number.size) == number) title.dropLast(number.size) else title
    return when {
        query == number || sameWords(title, query) || sameWords(name, query) -> NameMatch.Exact
        query.size <= title.size && startsWithWords(title, query) -> NameMatch.Start
        else -> NameMatch.None
    }
}

/** Every word of [s], normalised, stop words included. */
private fun words(s: String): List<String> {
    val folded = normalize(s)
    return tokenRanges(folded).map { folded.substring(it) }
}

private fun sameWord(word: String, query: String): Boolean = word == query || word == definiteBase(query)

private fun sameWords(words: List<String>, query: List<String>): Boolean =
    words.size == query.size && words.indices.all { sameWord(words[it], query[it]) }

/** The first words of [words] are [query]; the last query word may be the start of its word. */
private fun startsWithWords(words: List<String>, query: List<String>): Boolean = query.indices.all { i ->
    if (i == query.lastIndex) words[i].startsWith(query[i]) || sameWord(words[i], query[i]) else sameWord(words[i], query[i])
}

/** Ascending by the number's (year, ordinal), then as text; numbers without a year last. */
internal val ByNumber: Comparator<ListingItem> =
    compareBy<ListingItem> { numberKey(it.number) == null }
        .thenBy { numberKey(it.number)?.first }
        .thenBy { numberKey(it.number)?.second }
        .thenBy { it.number }

private val SFS_NUMBER = Regex("""(\d{4}):(\d+)""")
private val YEAR_AND_ORDINAL = Regex("""(1[6-9]\d\d|20\d\d)\D+(\d+)""")

/**
 * (year, ordinal) of a document number: the SFS form `1999:175` (any prefix, such as `N` or a series name),
 * else the first year (1600–2099) and the number after it; null when there is no year.
 */
internal fun numberKey(number: String): Pair<Int, Long>? {
    val match = SFS_NUMBER.find(number) ?: YEAR_AND_ORDINAL.find(number) ?: return null
    val year = match.groupValues[1].toInt()
    val ordinal = match.groupValues[2].take(MAX_ORDINAL_DIGITS).toLongOrNull() ?: return null
    return year to ordinal
}

private const val MAX_ORDINAL_DIGITS = 15

/**
 * [this] in [order]; stable, so ties keep their input order. By relevance, documents the query [text] names
 * ([nameMatch]) come first, so "brottsbalk" puts Brottsbalk (1962:700) ahead of newer case reports citing it.
 */
fun List<SearchHit>.sortedFor(order: SortOrder, text: String = ""): List<SearchHit> = when (order) {
    SortOrder.Relevance -> map { it to nameMatch(it.item, text) }
        .sortedWith(compareBy<Pair<SearchHit, NameMatch>> { it.second }.thenComparator { a, b -> ByFields.compare(a.first, b.first) })
        .map { it.first }
    SortOrder.Newest -> sortedWith(compareBy(NewestFirst) { it.item })
    SortOrder.Number -> sortedWith(compareBy(ByNumber) { it.item })
}

/**
 * Character ranges of [title] to highlight for [text]: every word that equals a query word or starts with one,
 * accent-insensitive ("are" marks "Åre"), and the base of a word with a definite ending ("miljöbalken" marks
 * "Miljöbalk"). Words the query drops (stop words, single letters) mark nothing.
 */
fun highlightRanges(title: String, text: String): List<IntRange> {
    val query = queryTerms(text)
    if (query.isEmpty()) return emptyList()
    val terms = query.map { it.text }
    val bases = query.mapNotNull { it.base }
    val folded = normalizeAligned(title)
    return tokenRanges(folded).filter { range ->
        val word = folded.substring(range)
        terms.any { word.startsWith(it) } || word in bases
    }
}
