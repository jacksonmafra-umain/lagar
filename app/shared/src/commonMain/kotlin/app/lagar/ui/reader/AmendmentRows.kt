package app.lagar.ui.reader

import app.lagar.data.DocumentMeta

/** One line of the reader's amendment list. Only [number] is known when the list falls back to `amended_by`. */
data class AmendmentRow(
    val number: String,
    val title: String? = null,
    val inForce: String? = null,
    val scope: String? = null,
)

/**
 * The amendments to list: the register's `amendments` when it has been read and lists any, otherwise
 * the SFS numbers of `amended_by`. The register value is raw when it is not a plain date
 * (`1983-07-01 överg.best.`, `den dag regeringen bestämmer`), so the raw text wins over the parsed date.
 */
fun amendmentRows(meta: DocumentMeta): List<AmendmentRow> {
    val register = meta.amendments
    if (!register.isNullOrEmpty()) {
        return register.map { AmendmentRow(it.number, it.title, it.inForceRaw ?: it.inForce, it.scope) }
    }
    return meta.amendedBy.map { AmendmentRow(it) }
}

private val SFS_NUMBER = Regex("""^(N?)(\d{4}):(\d+)$""")

/**
 * The document id the corpus gives an SFS number: `1983:240` is `sfs-1983-240`, `N2019:2` is
 * `sfs-n2019-2`. Null when [number] is not an SFS number.
 */
fun sfsDocumentId(number: String): String? {
    val match = SFS_NUMBER.matchEntire(number.trim()) ?: return null
    val (series, year, serial) = match.destructured
    return "sfs-${series.lowercase()}$year-$serial"
}
