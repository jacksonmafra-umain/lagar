package app.lagar.location

import androidx.compose.runtime.Composable
import app.lagar.domain.GeoPoint

/** What asking the platform for the device position gave. Only coarse accuracy is ever requested. */
sealed interface LocationResult {
    data class Found(val point: GeoPoint) : LocationResult

    /** The user refused, or the system blocks, location access for the app. */
    data object Denied : LocationResult

    /** Location services are off, unsupported, or produced no position. */
    data object Unavailable : LocationResult

    /** Access was granted but no position arrived within [LOCATION_FIX_TIMEOUT_MS]. */
    data object TimedOut : LocationResult
}

/** Asks for permission if needed, then for one coarse position. The position is never stored or sent anywhere. */
fun interface LocationRequester {
    suspend fun request(): LocationResult
}

/** How long to wait for a position once access is granted; the permission prompt itself is not timed. */
internal const val LOCATION_FIX_TIMEOUT_MS = 15_000L

/** A position up to this old is good enough to pick a kommun, so a cached one is used when there is one. */
internal const val LOCATION_MAX_AGE_MS = 10 * 60 * 1_000L

/** The platform's [LocationRequester], tied to the current screen for its permission prompt. */
@Composable
internal expect fun rememberLocationRequester(): LocationRequester
