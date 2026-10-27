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
