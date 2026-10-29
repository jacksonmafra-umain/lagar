package app.lagar.location

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import app.lagar.domain.GeoPoint
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

@Composable
internal actual fun rememberLocationRequester(): LocationRequester = remember { LocationRequester { requestPosition() } }

/** The browser's `GeolocationPositionError` codes; any other code (0 for no Geolocation API) is unavailable. */
private const val PERMISSION_DENIED = 1
private const val TIMEOUT = 3

/** One low-accuracy position; the browser runs the permission prompt and times only the fix itself. */
private suspend fun requestPosition(): LocationResult = suspendCancellableCoroutine { cont ->
    getCurrentPosition(
        onSuccess = { lat, lon -> if (cont.isActive) cont.resume(LocationResult.Found(GeoPoint(lat, lon))) },
        onError = { code ->
            val result = when (code) {
                PERMISSION_DENIED -> LocationResult.Denied
                TIMEOUT -> LocationResult.TimedOut
                else -> LocationResult.Unavailable
            }
            if (cont.isActive) cont.resume(result)
        },
        timeoutMs = LOCATION_FIX_TIMEOUT_MS.toInt(),
        maxAgeMs = LOCATION_MAX_AGE_MS.toInt(),
    )
}

private fun getCurrentPosition(
    onSuccess: (Double, Double) -> Unit,
    onError: (Int) -> Unit,
    timeoutMs: Int,
    maxAgeMs: Int,
): Unit = js(
    """{
    if (!navigator.geolocation) { onError(0); return; }
    navigator.geolocation.getCurrentPosition(
        function (p) { onSuccess(p.coords.latitude, p.coords.longitude); },
        function (e) { onError(e.code); },
        { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: maxAgeMs }
    );
}""",
)
