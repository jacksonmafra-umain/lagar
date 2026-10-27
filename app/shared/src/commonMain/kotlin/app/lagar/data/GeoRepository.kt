package app.lagar.data

import app.lagar.domain.Kommun
import app.lagar.domain.Region
import app.lagar.resources.Res
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** Serves the bundled SCB list of län and kommuner. */
class GeoRepository(
    private val readBytes: suspend (path: String) -> ByteArray = { Res.readBytes(it) },
) {
    private val json = Json { ignoreUnknownKeys = true }
    private var cached: Sweden? = null

    /** Län sorted by name in Swedish collation (å, ä, ö after z). */
    suspend fun regions(): List<Region> = load().regions.sortedWith(compareBy(SwedishCollation) { it.name })

    suspend fun kommuner(regionCode: String): List<Kommun> =
        load().kommuner.filter { it.regionCode == regionCode }.sortedWith(compareBy(SwedishCollation) { it.name })

    private suspend fun load(): Sweden = cached
        ?: json.decodeFromString<Sweden>(readBytes("files/geo/sweden.json").decodeToString()).also { cached = it }

    @Serializable
    private class Sweden(val regions: List<Region>, val kommuner: List<Kommun>)
}

/** Case-insensitive ordering where å, ä, ö sort after z; other letters keep their code point order. */
internal object SwedishCollation : Comparator<String> {
    private fun weight(c: Char): Int = when (val l = c.lowercaseChar()) {
        'å' -> 'z'.code + 1
        'ä' -> 'z'.code + 2
        'ö' -> 'z'.code + 3
        'é' -> 'e'.code
        else -> l.code
    }

    override fun compare(a: String, b: String): Int {
        for (i in 0 until minOf(a.length, b.length)) {
            val d = weight(a[i]) - weight(b[i])
            if (d != 0) return d
        }
        return a.length - b.length
    }
}
