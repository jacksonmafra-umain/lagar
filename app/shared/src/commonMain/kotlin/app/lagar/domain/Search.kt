package app.lagar.domain

import app.lagar.data.ListingItem
import kotlinx.datetime.LocalDate

enum class SearchMode { All, Title, Number }

enum class StatusFilter { All, InForce, Repealed }

/** [types] matches [ListingItem.type] (empty = all); [from] and [to] bound `issued` inclusively. */
data class SearchQuery(
    val text: String,
    val types: Set<String> = emptySet(),
    val from: LocalDate? = null,
    val to: LocalDate? = null,
    val mode: SearchMode = SearchMode.All,
    val status: StatusFilter = StatusFilter.All,
) {
    val isValidRange: Boolean get() = from == null || to == null || from <= to

    private val hasFilter: Boolean
        get() = types.isNotEmpty() || from != null || to != null || status != StatusFilter.All

    internal val isActive: Boolean get() = text.isNotBlank() || hasFilter
}

private const val ACCENTED = "åäöàáâãāăąçćčďđèéêëēėęěìíîïīįłñńňòóôõøōőŕřśšşťùúûūůűųýÿźżž"
private const val PLAIN = "aaoaaaaaaacccddeeeeeeeeiiiiiilnnnooooooorrssstuuuuuuuyyzzz"

/** Lowercases and folds diacritics, so "Åre" and "are" match; å/ä/ö become a/a/o. */
fun normalize(s: String): String = buildString(s.length) {
    for (c in s.lowercase()) {
        val i = ACCENTED.indexOf(c)
        append(if (i >= 0) PLAIN[i] else c)
    }
}

/** Keeps input order. Blank text with no other filter matches nothing; an inverted date range too. */
fun List<ListingItem>.search(q: SearchQuery): List<ListingItem> {
    if (!q.isValidRange || !q.isActive) return emptyList()
    val terms = normalize(q.text).split(Regex("\\s+")).filter { it.isNotEmpty() }
    return filter { it.matches(q, terms) }
}

private fun ListingItem.matches(q: SearchQuery, terms: List<String>): Boolean {
    if (q.types.isNotEmpty() && type !in q.types) return false
    when (q.status) {
        StatusFilter.All -> Unit
        StatusFilter.InForce -> if (repealed != null) return false
        StatusFilter.Repealed -> if (repealed == null) return false
    }
    if (q.from != null || q.to != null) {
        val date = issued?.let { runCatching { LocalDate.parse(it) }.getOrNull() } ?: return false
        if (q.from != null && date < q.from) return false
        if (q.to != null && date > q.to) return false
    }
    if (terms.isEmpty()) return true
    val titleText = normalize(title)
    val numberText = normalize(number)
    return terms.all { term ->
        when (q.mode) {
            SearchMode.Title -> term in titleText
            SearchMode.Number -> term in numberText
            SearchMode.All -> term in titleText || term in numberText
        }
    }
}
