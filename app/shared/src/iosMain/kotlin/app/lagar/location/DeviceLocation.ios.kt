package app.lagar.location

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import app.lagar.domain.GeoPoint
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.useContents
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import platform.CoreLocation.CLAuthorizationStatus
import platform.CoreLocation.CLLocation
import platform.CoreLocation.CLLocationManager
import platform.CoreLocation.CLLocationManagerDelegateProtocol
import platform.CoreLocation.kCLAuthorizationStatusAuthorizedAlways
import platform.CoreLocation.kCLAuthorizationStatusAuthorizedWhenInUse
import platform.CoreLocation.kCLAuthorizationStatusNotDetermined
import platform.CoreLocation.kCLErrorDenied
import platform.CoreLocation.kCLLocationAccuracyReduced
import platform.Foundation.NSDate
import platform.Foundation.NSError
import platform.Foundation.timeIntervalSinceDate
import platform.darwin.NSObject
import kotlin.coroutines.resume

@Composable
internal actual fun rememberLocationRequester(): LocationRequester = remember { LocationRequester { requestLocation() } }

/** Asks for when-in-use access if needed, then for one position at reduced (coarse) accuracy. */
private suspend fun requestLocation(): LocationResult = withContext(Dispatchers.Main) {
    val manager = CLLocationManager()
    manager.desiredAccuracy = kCLLocationAccuracyReduced
    if (!authorize(manager)) return@withContext LocationResult.Denied
    manager.location?.takeIf { it.ageMillis() <= LOCATION_MAX_AGE_MS }?.let { return@withContext LocationResult.Found(it.toGeoPoint()) }
    withTimeoutOrNull(LOCATION_FIX_TIMEOUT_MS) { locate(manager) } ?: LocationResult.TimedOut
}

private fun isAuthorized(status: CLAuthorizationStatus) =
    status == kCLAuthorizationStatusAuthorizedWhenInUse || status == kCLAuthorizationStatusAuthorizedAlways

/** True once access is granted; prompts when the user has not decided yet. Not timed: the user may take a while. */
private suspend fun authorize(manager: CLLocationManager): Boolean {
    if (manager.authorizationStatus != kCLAuthorizationStatusNotDetermined) return isAuthorized(manager.authorizationStatus)
    return suspendCancellableCoroutine { cont ->
        val delegate = AuthorizationDelegate(cont)
        manager.delegate = delegate
        cont.invokeOnCancellation { manager.delegate = null }
        manager.requestWhenInUseAuthorization()
    }.also { manager.delegate = null }
}

private class AuthorizationDelegate(
    private val cont: CancellableContinuation<Boolean>,
) : NSObject(),
    CLLocationManagerDelegateProtocol {
    override fun locationManagerDidChangeAuthorization(manager: CLLocationManager) {
        val status = manager.authorizationStatus
        // The first callback arrives when the delegate is set, before the user answers.
        if (status != kCLAuthorizationStatusNotDetermined && cont.isActive) cont.resume(isAuthorized(status))
    }
}

private suspend fun locate(manager: CLLocationManager): LocationResult = suspendCancellableCoroutine { cont ->
    val delegate = PositionDelegate(cont)
    manager.delegate = delegate
    cont.invokeOnCancellation {
        manager.stopUpdatingLocation()
        manager.delegate = null
    }
    manager.requestLocation()
}

private class PositionDelegate(
    private val cont: CancellableContinuation<LocationResult>,
) : NSObject(),
    CLLocationManagerDelegateProtocol {
    override fun locationManager(manager: CLLocationManager, didUpdateLocations: List<*>) {
        val location = didUpdateLocations.lastOrNull() as? CLLocation
        finish(manager, location?.let { LocationResult.Found(it.toGeoPoint()) } ?: LocationResult.Unavailable)
    }

    override fun locationManager(manager: CLLocationManager, didFailWithError: NSError) {
        finish(manager, if (didFailWithError.code == kCLErrorDenied) LocationResult.Denied else LocationResult.Unavailable)
    }

    private fun finish(manager: CLLocationManager, result: LocationResult) {
        manager.delegate = null
        if (cont.isActive) cont.resume(result)
    }
}

private fun CLLocation.ageMillis(): Long = (NSDate().timeIntervalSinceDate(timestamp) * 1_000).toLong()

@OptIn(ExperimentalForeignApi::class)
private fun CLLocation.toGeoPoint(): GeoPoint = coordinate.useContents { GeoPoint(latitude, longitude) }
