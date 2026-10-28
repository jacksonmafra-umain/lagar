package app.lagar.ui.reader

private const val CHAPTER_PREFIX = "## "

/**
 * Splits a document body into one section per `## ` chapter heading, so the reader can render a
 * long statute lazily. Anything before the first chapter (the `# title`, a preamble) stays in the
 * first section; a body with no `## ` heading is a single section. Joining the result with `\n`
 * gives the body back.
 */
fun splitSections(body: String): List<String> {
    if (body.isEmpty()) return emptyList()
    val lines = body.split('\n')
    val starts = lines.indices.filter { lines[it].startsWith(CHAPTER_PREFIX) }
    // The first chapter opens the first section together with whatever precedes it.
    val cuts = starts.drop(1)
    val bounds = listOf(0) + cuts + lines.size
    return bounds.zipWithNext { from, to -> lines.subList(from, to).joinToString("\n") }
}

/** Drops a leading `# title` line from the first section; the metadata header already shows the title. */
fun withoutTitle(section: String): String {
    if (!section.startsWith("# ")) return section
    return section.substringAfter('\n', missingDelimiterValue = "").trimStart('\n')
}

// `**1 §**`, `**3 a §**`, `**4 §§**`: a statute number in bold at the start of a line.
private val STATUTE_START = Regex("""^\*\*\d+\s?[a-z]?\s§§?\*\*""")

/** True when [block] opens with a bold statute number, i.e. it is one numbered statute (§). */
fun isStatuteBlock(block: String): Boolean = STATUTE_START.containsMatchIn(block)

/**
 * Splits a section into blocks for the reader's lazy list: a new block starts at every line that
 * opens with a bold statute number (`**1 §**`) and at every heading line. Text before the first
 * statute (a chapter heading, a preamble) is its own block. Joining with `\n` gives the section back.
 */
fun splitParagraphs(section: String): List<String> {
    if (section.isEmpty()) return emptyList()
    val lines = section.split('\n')
    val starts = lines.indices.filter { it > 0 && (STATUTE_START.containsMatchIn(lines[it]) || lines[it].startsWith("#")) }
    val bounds = listOf(0) + starts + lines.size
    return bounds.zipWithNext { from, to -> lines.subList(from, to).joinToString("\n") }
}
