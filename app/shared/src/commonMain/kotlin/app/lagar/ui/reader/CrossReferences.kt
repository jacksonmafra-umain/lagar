package app.lagar.ui.reader

/**
 * A citation of another document in legal text: the characters from [start] (inclusive) to [end]
 * (exclusive) name the document with id [id]. The range is what the reader underlines, e.g.
 * `lagen (1962:700)`, `Lag (1994:458)`, `SFS 1998:808` or `NJA 2026:38`.
 */
data class CitationRef(val start: Int, val end: Int, val id: String)

// An SFS number as it appears in running text: `1962:700`, `N2019:2`. Its context decides whether it is a citation.
private val SFS_IN_TEXT = Regex("""N?\d{4}:\d+""")

// A case-law report reference opens with a court series and a year: `NJA 2026:38`, `HFD 2026 ref. 43`.
private val CASE_SERIES = Regex("""(?:NJA|HFD|RÅ|AD|MÖD|PMÖD|MIG|MD|RH) \d{4}""")

// The parts that can follow the year of a case reference, before its serial number.
private val CASE_SERIAL_MARKERS = listOf(":", " ref. ", " not. ", " s. ")

/**
 * Endings of a word that names a statute, so the SFS number after it is a citation: `lagen`,
 * `brottsbalken`, `förordningen`, `regeringsformen`, `riksdagsordningen`, `Lag` in an amendment note.
 */
private val LAW_WORD_ENDINGS = listOf(
    "lag", "lagen", "lagar", "lagarna",
    "balk", "balken",
    "förordning", "förordningen", "förordningar", "förordningarna",
    "kungörelse", "kungörelsen", "kungörelser", "kungörelserna",
    "stadga", "stadgan",
    "ordning", "ordningen",
    "formen",
    "instruktion", "instruktionen",
    "reglemente", "reglementet",
    "tillkännagivande", "tillkännagivandet",
)

private fun isLawWord(word: String): Boolean {
    val lower = word.lowercase()
    return LAW_WORD_ENDINGS.any { lower.endsWith(it) }
}

private fun isWordChar(c: Char): Boolean = c.isLetterOrDigit() || c == '-'

/** Start of the word that ends right before [end] (exclusive), or [end] when there is none. */
private fun wordStartBefore(text: String, end: Int): Int {
    var i = end
    while (i > 0 && isWordChar(text[i - 1])) i--
    return i
}

/** Index after skipping spaces backwards from [end] (exclusive). Only spaces: a citation never spans lines. */
private fun skipSpacesBack(text: String, end: Int): Int {
    var i = end
    while (i > 0 && (text[i - 1] == ' ' || text[i - 1] == ' ')) i--
    return i
}

/**
 * Finds the citations of SFS statutes and case-law reports in [text], in text order and without
 * overlaps. An SFS number counts as a citation only in these forms, so that numbers in other series
 * (`SÖ 1987:87`, `SKOLFS 2011:144`) and dates stay plain:
 * - in parentheses after a word that names a statute: `lagen (1962:700)`, `Lag (1994:458).`;
 *   the word and the parentheses are part of the range;
 * - alone in parentheses, or after `SFS`: `(2001:1063)`, `(SFS 1998:808)`, `SFS 1998:808`;
 * - after a statute word without parentheses: `Förordning 1995:908`, `lagen 1962:700`.
 * Section references such as `1 kap. 3 §` carry no SFS number and are never matched.
 */
fun findCitations(text: String): List<CitationRef> {
    val found = (sfsCitations(text) + caseCitations(text)).sortedBy { it.start }
    val result = mutableListOf<CitationRef>()
    for (ref in found) {
        if (result.isEmpty() || ref.start >= result.last().end) result += ref
    }
    return result
}

private fun sfsCitations(text: String): List<CitationRef> = SFS_IN_TEXT.findAll(text).mapNotNull { match ->
    val start = match.range.first
    val end = match.range.last + 1
    if (start > 0 && (isWordChar(text[start - 1]) || text[start - 1] == ':' || text[start - 1] == '.')) return@mapNotNull null
    if (end < text.length && (isWordChar(text[end]) || text[end] == ':')) return@mapNotNull null
    val id = sfsDocumentId(match.value) ?: return@mapNotNull null

    // `SFS 1998:808`: the series name joins the range.
    var inner = start
    val beforeNumber = skipSpacesBack(text, start)
    val wordStart = wordStartBefore(text, beforeNumber)
    val word = text.substring(wordStart, beforeNumber)
    if (word == "SFS" && beforeNumber < start) inner = wordStart

    val open = inner - 1
    if (open >= 0 && text[open] == '(') {
        val closed = end < text.length && text[end] == ')'
        val lawEnd = skipSpacesBack(text, open)
        val lawStart = wordStartBefore(text, lawEnd)
        val lawWord = text.substring(lawStart, lawEnd)
        return@mapNotNull if (closed && lawWord.isNotEmpty() && isLawWord(lawWord)) {
            CitationRef(lawStart, end + 1, id)
        } else {
            CitationRef(inner, end, id)
        }
    }
    when {
        inner != start -> CitationRef(inner, end, id)
        beforeNumber < start && word.isNotEmpty() && isLawWord(word) -> CitationRef(wordStart, end, id)
        else -> null
    }
}.toList()

private fun caseCitations(text: String): List<CitationRef> = CASE_SERIES.findAll(text).mapNotNull { match ->
    val start = match.range.first
    if (start > 0 && isWordChar(text[start - 1])) return@mapNotNull null
    val afterYear = match.range.last + 1
    val marker = CASE_SERIAL_MARKERS.firstOrNull { text.startsWith(it, afterYear) } ?: return@mapNotNull null
    val serialStart = afterYear + marker.length
    var end = serialStart
    while (end < text.length && text[end].isDigit()) end++
    if (end == serialStart || (end < text.length && (text[end].isLetter() || text[end] == ':'))) return@mapNotNull null
    CitationRef(start, end, caseLawDocumentId(text.substring(start, end)))
}.toList()

private val SLUG_FOLD = mapOf('å' to 'a', 'ä' to 'a', 'ö' to 'o', 'é' to 'e', 'ü' to 'u')

/**
 * The document id the corpus gives a case-law report number, the same slug the collector writes:
 * `NJA 2026:38` is `nja-2026-38`, `HFD 2026 ref. 43` is `hfd-2026-ref-43`, `RÅ 2010 ref. 5` is `ra-2010-ref-5`.
 */
fun caseLawDocumentId(number: String): String {
    val folded = number.lowercase().map { SLUG_FOLD[it] ?: it }
    val out = StringBuilder()
    var dash = false
    for (c in folded) {
        if (c in '0'..'9' || c in 'a'..'z') {
            if (dash && out.isNotEmpty()) out.append('-')
            out.append(c)
            dash = false
        } else {
            dash = true
        }
    }
    return out.toString()
}

/** The ids of every document [text] cites, for the existence check before linking. */
fun citedDocumentIds(text: String): Set<String> = findCitations(text).mapTo(LinkedHashSet()) { it.id }

/** Destination prefix of the Markdown links [linkCitations] writes; the reader opens the id after it. */
const val CROSS_REFERENCE_SCHEME = "lagar-doc:"

/**
 * Rewrites [markdown] so that each citation of a document in [targets] becomes a Markdown link
 * `[lagen (1962:700)](lagar-doc:sfs-1962-700)`. Citations of other documents stay plain text.
 */
fun linkCitations(markdown: String, targets: Set<String>): String {
    if (targets.isEmpty()) return markdown
    val refs = findCitations(markdown).filter { it.id in targets }
    if (refs.isEmpty()) return markdown
    val out = StringBuilder(markdown.length + refs.size * 32)
    var last = 0
    for (ref in refs) {
        out.append(markdown, last, ref.start)
        out.append('[').append(markdown, ref.start, ref.end).append("](").append(CROSS_REFERENCE_SCHEME).append(ref.id).append(')')
        last = ref.end
    }
    out.append(markdown, last, markdown.length)
    return out.toString()
}
