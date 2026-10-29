package app.lagar.ui.onboarding

import app.lagar.domain.Kommun
import app.lagar.domain.KommunCentroid
import app.lagar.domain.Locality
import app.lagar.domain.nearestKommun
import app.lagar.location.LocationRequester
import app.lagar.location.LocationResult
import kotlinx.coroutines.CancellationException

/** State of the "Use my location" action in the locality pickers. */
sealed interface LocationSuggestion {
    data object Idle : LocationSuggestion

    data object Locating : LocationSuggestion

    /** The kommun nearest to the device; the pickers pre-select it and the user confirms or changes it. */
    data class Suggested(val kommun: Kommun) : LocationSuggestion {
        val locality: Locality get() = Locality(kommun.regionCode, kommun.code)
    }

    data class Failed(val reason: Reason) : LocationSuggestion

    enum class Reason { Denied, Unavailable, TimedOut, OutsideSweden }
}

/** Maps a platform [result] to a suggestion: the nearest kommun, or why there is none. */
internal fun suggestionFor(result: LocationResult, centroids: List<KommunCentroid>): LocationSuggestion = when (result) {
    is LocationResult.Found -> nearestKommun(result.point, centroids)
        ?.let { LocationSuggestion.Suggested(it.kommun) }
        ?: LocationSuggestion.Failed(LocationSuggestion.Reason.OutsideSweden)
    LocationResult.Denied -> LocationSuggestion.Failed(LocationSuggestion.Reason.Denied)
    LocationResult.Unavailable -> LocationSuggestion.Failed(LocationSuggestion.Reason.Unavailable)
    LocationResult.TimedOut -> LocationSuggestion.Failed(LocationSuggestion.Reason.TimedOut)
}

/** Requests one position and turns it into a suggestion; any platform failure reads as unavailable. */
internal suspend fun suggestKommun(
    requester: LocationRequester,
    centroids: suspend () -> List<KommunCentroid>,
): LocationSuggestion = try {
    suggestionFor(requester.request(), centroids())
} catch (e: CancellationException) {
    throw e
} catch (_: Exception) {
    LocationSuggestion.Failed(LocationSuggestion.Reason.Unavailable)
}
