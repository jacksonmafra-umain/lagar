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
internal val STATUTE_START = Regex("""^\*\*\d+\s?[a-z]?\s§§?\*\*""")

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

/**
 * The blocks the reader lists, one lazy item each: the body split per chapter and per statute, the
 * leading `# title` dropped (the metadata header shows it) and blank blocks removed.
 */
fun readerBlocks(body: String): List<String> = splitSections(body).flatMapIndexed { index, section ->
    splitParagraphs(if (index == 0) withoutTitle(section) else section)
}.filter { it.isNotBlank() }

private val WHITESPACE = Regex("""\s+""")

/**
 * The number of a numbered statute or chapter, as words: `3` or `3 a` followed by [marker] (`§`, `§§`,
 * `kap.`). Parsed by splitting on whitespace rather than with optional regex groups, whose captures
 * Kotlin/Wasm keeps after backtracking (`1 kap.` would read as chapter `1k`).
 */
private fun numberBefore(words: List<String>, marker: (String) -> Boolean): String? {
    val digits = words.getOrNull(0)?.takeIf { it.isNotEmpty() && it.all(Char::isDigit) } ?: return null
    val second = words.getOrNull(1) ?: return null
    if (marker(second)) return digits
    val letter = second.singleOrNull()?.takeIf { it in 'a'..'z' } ?: return null
    return if (words.getOrNull(2)?.let(marker) == true) "$digits $letter" else null
}

// `## 1 kap. Om brott`, `## 2 a kap. ...`: `1`, `2 a`.
private fun chapterNumber(heading: String): String? =
    numberBefore(heading.removePrefix(CHAPTER_PREFIX).trim().split(WHITESPACE)) { it.startsWith("kap.") }

// `**3 §** Text`, `**3 a §** Text`, `**4 §§**`: `3`, `3 a`, `4`.
private fun statuteNumber(block: String): String? {
    val opening = STATUTE_START.find(block)?.value ?: return null
    return numberBefore(opening.removeSurrounding("**").trim().split(WHITESPACE)) { it == "§" || it == "§§" }
}

/** One chapter in the table of contents; [anchor] null for the statutes before the first chapter. */
data class OutlineChapter(
    val title: String?,
    val anchor: String?,
    val blockIndex: Int,
    val statutes: List<OutlineStatute>,
)

/** One numbered statute; [label] is how the text writes it (`3 a §`), [anchor] is unique in the document. */
data class OutlineStatute(val label: String, val anchor: String, val blockIndex: Int)

/**
 * The document's table of contents, built from [readerBlocks]: chapters (`## ` headings) with their
 * numbered statutes. Each entry carries an anchor for deep links and the index of its block.
 */
data class Outline(val chapters: List<OutlineChapter>) {
    private val byAnchor: Map<String, Int> = buildMap {
        chapters.forEach { chapter ->
            chapter.anchor?.let { put(it, chapter.blockIndex) }
            chapter.statutes.forEach { put(it.anchor, it.blockIndex) }
        }
    }
    private val byBlock: Map<Int, String> = byAnchor.entries.associate { it.value to it.key }

    /** The block a deep link [anchor] points at, or null when the document has no such anchor. */
    fun blockOf(anchor: String): Int? = byAnchor[anchor]

    /** The anchor of the block at [blockIndex], or null when it is neither a chapter nor a statute. */
    fun anchorOf(blockIndex: Int): String? = byBlock[blockIndex]

    /** The chapter that contains [blockIndex], or null before the first chapter. */
    fun chapterOf(blockIndex: Int): OutlineChapter? = chapters.lastOrNull { it.anchor != null && it.blockIndex <= blockIndex }

    val isEmpty: Boolean get() = chapters.all { it.anchor == null && it.statutes.isEmpty() }
}

/**
 * Anchors are short and URL-safe: a chapter is `k3` (`k2a` for `2 a kap.`), an unnumbered heading
 * such as `## Övergångsbestämmelser` is `h1`, `h2`, ... in order, and a statute is its chapter's
 * anchor followed by `p` and the number (`k3p1`, `k3p1a`; `p4` before any chapter). A number that
 * repeats within a chapter (a provision with a pending new wording) gets `-2`, `-3`, ...
 */
fun buildOutline(blocks: List<String>): Outline {
    val chapters = mutableListOf<OutlineChapter>()
    val used = mutableSetOf<String>()
    var headings = 0
    var title: String? = null
    var anchor: String? = null
    var start = 0
    var statutes = mutableListOf<OutlineStatute>()

    fun unique(base: String): String {
        var candidate = base
        var n = 1
        while (!used.add(candidate)) candidate = "$base-${++n}"
        return candidate
    }

    fun close() {
        if (anchor != null || statutes.isNotEmpty()) chapters += OutlineChapter(title, anchor, start, statutes)
    }

    blocks.forEachIndexed { index, block ->
        val firstLine = block.substringBefore('\n')
        if (firstLine.startsWith(CHAPTER_PREFIX)) {
            close()
            val number = chapterNumber(firstLine)
            title = firstLine.removePrefix(CHAPTER_PREFIX).trim()
            anchor = unique(if (number != null) "k" + number.replace(" ", "") else "h${++headings}")
            start = index
            statutes = mutableListOf()
            return@forEachIndexed
        }
        val number = statuteNumber(block) ?: return@forEachIndexed
        statutes += OutlineStatute("$number §", unique((anchor ?: "") + "p" + number.replace(" ", "")), index)
    }
    close()
    return Outline(chapters)
}

/** A readable name for the block at [blockIndex], e.g. `3 kap. 1 §`, for share texts and labels. */
fun Outline.labelOf(blockIndex: Int): String? {
    val chapter = chapterOf(blockIndex)
    val statute = chapters.firstNotNullOfOrNull { c -> c.statutes.firstOrNull { it.blockIndex == blockIndex } }
    val chapterNumber = chapter?.anchor?.takeIf { it.startsWith("k") }?.let { chapterLabel(it.removePrefix("k")) }
    return when {
        statute != null && chapterNumber != null -> "$chapterNumber ${statute.label}"
        statute != null -> statute.label
        chapter != null && chapter.blockIndex == blockIndex -> chapter.title
        else -> null
    }
}

// `2a` -> `2 a kap.`
private fun chapterLabel(number: String): String {
    val digits = number.takeWhile { it.isDigit() }
    val letter = number.drop(digits.length).substringBefore('-')
    return if (letter.isEmpty()) "$digits kap." else "$digits $letter kap."
}
