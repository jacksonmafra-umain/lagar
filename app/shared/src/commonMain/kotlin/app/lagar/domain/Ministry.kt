package app.lagar.domain

// "Justitiedepartementet L5": the unit code after the ministry name is dropped, as in the API's by-ministry grouping.
private val MinistryPattern = Regex("""(.*?departementet)\b.*""")

/**
 * The ministry a `ministry` value belongs to, without the unit code, as the API groups it (docs/api.md, "By
 * ministry"): whitespace collapsed, and for a ministry (`…departementet`) whatever follows the name dropped. Other
 * bodies are kept as written; null when [value] is null or blank.
 */
fun ministryName(value: String?): String? {
    if (value.isNullOrBlank()) return null
    val collapsed = value.trim().split(Regex("""\s+""")).joinToString(" ")
    return MinistryPattern.matchEntire(collapsed)?.groupValues?.get(1) ?: collapsed
}
