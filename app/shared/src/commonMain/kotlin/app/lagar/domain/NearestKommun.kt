package app.lagar.domain

import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** A WGS 84 position in degrees. */
data class GeoPoint(val lat: Double, val lon: Double)

/**
 * The area centroid of a [kommun] and the distance from it to the farthest point of its boundary, both derived from
 * SCB's kommun boundaries.
 */
data class KommunCentroid(val kommun: Kommun, val center: GeoPoint, val radiusKm: Int)

private const val EARTH_RADIUS_KM = 6371.0088

/** Great-circle distance between two points, in km. */
fun haversineKm(a: GeoPoint, b: GeoPoint): Double {
    val p1 = a.lat.toRadians()
    val p2 = b.lat.toRadians()
    val dp = p2 - p1
    val dl = (b.lon - a.lon).toRadians()
    val h = sin(dp / 2).let { it * it } + cos(p1) * cos(p2) * sin(dl / 2).let { it * it }
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h.coerceIn(0.0, 1.0)))
}

/**
 * The kommun whose centroid is nearest to [point], or null when [point] lies outside every kommun's radius, which
 * means it is outside Sweden. A point inside a kommun is always within that kommun's radius, so no Swedish position
 * is rejected; near a boundary the nearest centroid can belong to the neighbour, which is why this is only offered
 * as a suggestion.
 */
fun nearestKommun(point: GeoPoint, centroids: List<KommunCentroid>): KommunCentroid? {
    val distances = centroids.map { it to haversineKm(point, it.center) }
    if (distances.none { (centroid, km) -> km <= centroid.radiusKm }) return null
    return distances.minByOrNull { it.second }?.first
}

private fun Double.toRadians(): Double = this * kotlin.math.PI / 180.0
