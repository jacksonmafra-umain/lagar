package app.lagar.ui.navigation

/** The published web app; shared links point here so they open on any device. */
const val WEB_APP_URL = "https://jacksonmafra-umain.github.io/lagar/"

private val DOCUMENT_ID = Regex("""^[a-z0-9_]+-[0-9a-z-]+$""")
private val ANCHOR = Regex("""^[a-z0-9-]{1,32}$""")

/**
 * A link to [id] in the web app at [base] (`https://…/lagar/`), optionally at the outline [anchor]:
 * `?doc=sfs-1962-700&p=k3p1`. Ids and anchors are URL-safe, so nothing needs escaping.
 */
fun readerLink(base: String, id: String, anchor: String? = null): String {
    val root = base.substringBefore('#').substringBefore('?')
    return buildString {
        append(root).append("?doc=").append(id)
        if (anchor != null) append("&p=").append(anchor)
    }
}

/**
 * The [Reader] route a link's query string asks for (`?doc=<id>&p=<anchor>`, with or without the
 * leading `?`), or null when there is no valid `doc`. An invalid `p` is dropped, keeping the document.
 */
fun parseReaderLink(query: String): Reader? {
    val params = query.removePrefix("?").split('&').mapNotNull { pair ->
        val key = pair.substringBefore('=', missingDelimiterValue = "")
        if (key.isEmpty()) null else key to pair.substringAfter('=')
    }.toMap()
    val id = params["doc"]?.takeIf { DOCUMENT_ID.matches(it) } ?: return null
    val anchor = params["p"]?.takeIf { ANCHOR.matches(it) }
    return Reader(id, anchor)
}
