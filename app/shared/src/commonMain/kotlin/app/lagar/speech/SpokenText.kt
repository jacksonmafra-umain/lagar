package app.lagar.speech

/** The longest piece handed to the platform at once; some engines stop or refuse after a few hundred characters. */
internal const val MAX_CHUNK = 220

private val LINK = Regex("""\[([^\]]*)]\([^)]*\)""")
private val HEADING = Regex("""^#+\s*""")
private val BULLET = Regex("""^[-*+]\s+""")
private val WHITESPACE = Regex("""\s+""")
private val SECTION = Regex("""(\d+(?: [a-z])?) §""")
private val CHAPTER = Regex("""(\d+(?: [a-z])?) kap\.""")

/** The words of a block of legal Markdown as they should be heard: no link targets, emphasis or heading marks. */
fun spokenText(markdown: String): String = markdown
    .replace(LINK, "$1")
    .lines()
    .map { it.trim().replace(HEADING, "").replace(BULLET, "") }
    .filter { it.isNotEmpty() }
    .joinToString(" ")
    .replace("**", "")
    .replace("*", "")
    .replace(WHITESPACE, " ")
    .trim()

/** [text] with the signs a voice would spell out written as words: `3 §` is "3 paragrafen", `12 kap.` "12 kapitlet". */
fun spokenWords(text: String): String = text
    .replace("§§", "paragraferna")
    .replace(SECTION, "$1 paragrafen")
    .replace("§", "paragraf")
    .replace(CHAPTER, "$1 kapitlet")
    .replace("kap.", "kapitel")

/**
 * [text] cut into pieces of at most [maxLength] characters for the engine: whole sentences where they fit, else
 * clauses at a comma, semicolon or colon, else words. Joined with spaces, the pieces give the text back.
 */
fun speechChunks(text: String, maxLength: Int = MAX_CHUNK): List<String> {
    val clean = text.replace(WHITESPACE, " ").trim()
    if (clean.isEmpty()) return emptyList()
    val units = splitAfter(clean, ".!?").flatMap { sentence ->
        if (sentence.length <= maxLength) {
            listOf(sentence)
        } else {
            splitAfter(sentence, ",;:").flatMap { if (it.length <= maxLength) listOf(it) else wrapWords(it, maxLength) }
        }
    }
    val chunks = mutableListOf<String>()
    val current = StringBuilder()
    for (unit in units) {
        if (current.isNotEmpty() && current.length + 1 + unit.length > maxLength) {
            chunks += current.toString()
            current.clear()
        }
        if (current.isNotEmpty()) current.append(' ')
        current.append(unit)
    }
    if (current.isNotEmpty()) chunks += current.toString()
    return chunks
}

/** Runs of words in [text], each ending at a word whose last character is one of [marks] (or at the end). */
private fun splitAfter(text: String, marks: String): List<String> {
    val out = mutableListOf<String>()
    val current = mutableListOf<String>()
    for (word in text.split(' ')) {
        current += word
        if (word.lastOrNull()?.let { it in marks } == true) {
            out += current.joinToString(" ")
            current.clear()
        }
    }
    if (current.isNotEmpty()) out += current.joinToString(" ")
    return out
}

/** [text] packed word by word into lines of at most [maxLength]; a longer word is cut. */
private fun wrapWords(text: String, maxLength: Int): List<String> {
    val out = mutableListOf<String>()
    val current = StringBuilder()
    for (word in text.split(' ').flatMap { it.chunked(maxLength) }) {
        if (current.isNotEmpty() && current.length + 1 + word.length > maxLength) {
            out += current.toString()
            current.clear()
        }
        if (current.isNotEmpty()) current.append(' ')
        current.append(word)
    }
    if (current.isNotEmpty()) out += current.toString()
    return out
}
