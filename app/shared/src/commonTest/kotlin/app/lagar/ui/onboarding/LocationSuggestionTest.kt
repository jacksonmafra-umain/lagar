package app.lagar.ui.onboarding

import app.lagar.domain.GeoPoint
import app.lagar.domain.Kommun
import app.lagar.domain.KommunCentroid
import app.lagar.domain.Locality
import app.lagar.location.LocationRequester
import app.lagar.location.LocationResult
import app.lagar.ui.onboarding.LocationSuggestion.Failed
import app.lagar.ui.onboarding.LocationSuggestion.Reason
import app.lagar.ui.onboarding.LocationSuggestion.Suggested
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals

class LocationSuggestionTest {
    private val goteborg = Kommun("1480", "Göteborg", "14")
    private val centroids = listOf(
        KommunCentroid(goteborg, GeoPoint(57.744, 11.979), 21),
        KommunCentroid(Kommun("0180", "Stockholm", "01"), GeoPoint(59.323, 18.0), 15),
    )

    @Test
    fun foundPositionSuggestsTheNearestKommunAndItsRegion() {
        val suggestion = suggestionFor(LocationResult.Found(GeoPoint(57.70, 11.97)), centroids)
        assertEquals(Suggested(goteborg), suggestion)
        assertEquals(Locality("14", "1480"), (suggestion as Suggested).locality)
    }

    @Test
    fun positionAbroadIsOutsideSweden() {
        assertEquals(Failed(Reason.OutsideSweden), suggestionFor(LocationResult.Found(GeoPoint(48.85, 2.35)), centroids))
    }

    @Test
    fun platformFailuresMapToTheirReasons() {
        assertEquals(Failed(Reason.Denied), suggestionFor(LocationResult.Denied, centroids))
        assertEquals(Failed(Reason.Unavailable), suggestionFor(LocationResult.Unavailable, centroids))
        assertEquals(Failed(Reason.TimedOut), suggestionFor(LocationResult.TimedOut, centroids))
    }

    @Test
    fun suggestKommunUsesTheRequester() = runTest {
        val requester = LocationRequester { LocationResult.Found(GeoPoint(59.33, 18.07)) }
        assertEquals(Suggested(centroids[1].kommun), suggestKommun(requester) { centroids })
    }

    @Test
    fun throwingRequesterOrDataIsUnavailable() = runTest {
        val failing = LocationRequester { error("no provider") }
        assertEquals(Failed(Reason.Unavailable), suggestKommun(failing) { centroids })
        val found = LocationRequester { LocationResult.Found(GeoPoint(59.33, 18.07)) }
        assertEquals(Failed(Reason.Unavailable), suggestKommun(found) { error("missing file") })
    }
}
