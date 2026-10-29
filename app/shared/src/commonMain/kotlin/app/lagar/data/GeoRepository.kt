package app.lagar.data

import app.lagar.domain.GeoPoint
import app.lagar.domain.Kommun
import app.lagar.domain.KommunCentroid
import app.lagar.domain.Locality
import app.lagar.domain.Region
import app.lagar.domain.Scope
import app.lagar.resources.Res
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/** Serves the bundled SCB list of län and kommuner, with each kommun's centroid. */
class GeoRepository(
    private val readBytes: suspend (path: String) -> ByteArray = { Res.readBytes(it) },
) {
    private val json = Json { ignoreUnknownKeys = true }
    private var cached: Sweden? = null

    /** Län sorted by name in Swedish collation (å, ä, ö after z). */
    suspend fun regions(): List<Region> = load().regions.sortedWith(compareBy(SwedishCollation) { it.name })

    suspend fun kommuner(regionCode: String): List<Kommun> = load().kommuner
        .filter { it.regionCode == regionCode }
        .map { it.toKommun() }
        .sortedWith(compareBy(SwedishCollation) { it.name })

    /** Centroids of every kommun that has one in the bundled file. */
    suspend fun centroids(): List<KommunCentroid> = load().kommuner.mapNotNull { entry ->
        val lat = entry.lat ?: return@mapNotNull null
        val lon = entry.lon ?: return@mapNotNull null
        KommunCentroid(entry.toKommun(), GeoPoint(lat, lon), entry.radiusKm ?: 0)
    }

    /** Name of the län (Region) or kommun (Kommun) the [locality] selects for [scope]; null for Nationell or when unset. */
    suspend fun localityName(scope: Scope, locality: Locality): String? = when (scope) {
        Scope.Nationell -> null
        Scope.Region -> locality.regionCode?.let { code -> regions().firstOrNull { it.code == code }?.name }
        Scope.Kommun -> locality.regionCode?.let { region ->
            kommuner(region).firstOrNull { it.code == locality.kommunCode }?.name
        }
    }

    private suspend fun load(): Sweden = cached
        ?: json.decodeFromString<Sweden>(readBytes("files/geo/sweden.json").decodeToString()).also { cached = it }

    @Serializable
    private class Sweden(val regions: List<Region>, val kommuner: List<KommunEntry>)

    @Serializable
    private class KommunEntry(
        val code: String,
        val name: String,
        val regionCode: String,
        val lat: Double? = null,
        val lon: Double? = null,
        val radiusKm: Int? = null,
    ) {
        fun toKommun() = Kommun(code, name, regionCode)
    }
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
