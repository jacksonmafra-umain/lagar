package app.lagar.ui.reader

private val LEADING_NUMBER = Regex("""^\d+\s?[a-z]?\s§§?\s*""")
private val MARKUP = Regex("""[*_`]+""")
private val SPACES = Regex("""\s+""")

/**
 * The start of a § or chapter as plain text, for a saved provision: markdown marks and a leading heading `#` or
 * statute number (`3 §`) dropped, whitespace collapsed, cut at a word boundary to at most [max] characters
 * with an ellipsis.
 */
fun provisionExcerpt(block: String, max: Int = EXCERPT_LENGTH): String {
    val text = block.lineSequence()
        .map { it.trimStart('#', ' ', '>', '-') }
        .joinToString(" ")
        .replace(MARKUP, "")
        .replace(SPACES, " ")
        .trim()
        .replaceFirst(LEADING_NUMBER, "")
    if (text.length <= max) return text
    val cut = text.take(max).substringBeforeLast(' ').ifEmpty { text.take(max) }
    return cut.trimEnd(',', ';', ':', '.', ' ') + "…"
}

/** A short one-paragraph preview of a note, cut like [provisionExcerpt]. */
fun notePreview(text: String, max: Int = NOTE_PREVIEW_LENGTH): String = provisionExcerpt(text.replace(SPACES, " "), max)

private const val EXCERPT_LENGTH = 160
private const val NOTE_PREVIEW_LENGTH = 120
