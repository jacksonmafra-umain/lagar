package app.lagar.location

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.os.Build
import android.os.SystemClock
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.core.location.LocationManagerCompat
import androidx.core.os.CancellationSignal
import app.lagar.domain.GeoPoint
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

@Composable
internal actual fun rememberLocationRequester(): LocationRequester {
    val context = LocalContext.current.applicationContext
    val pending = remember { PendingPermission() }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        pending.complete(granted)
    }
    return remember(context, launcher) {
        LocationRequester {
            val granted = hasCoarsePermission(context) ||
                pending.await { launcher.launch(Manifest.permission.ACCESS_COARSE_LOCATION) }
            if (granted) currentLocation(context) else LocationResult.Denied
        }
    }
}

/** Bridges the permission launcher's callback to a suspending call. */
private class PendingPermission {
    private var deferred: CompletableDeferred<Boolean>? = null

    suspend fun await(launch: () -> Unit): Boolean {
        val next = CompletableDeferred<Boolean>()
        deferred?.cancel()
        deferred = next
        launch()
        return next.await()
    }

    fun complete(granted: Boolean) {
        deferred?.complete(granted)
        deferred = null
    }
}

private fun hasCoarsePermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

private suspend fun currentLocation(context: Context): LocationResult {
    val manager = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
        ?: return LocationResult.Unavailable
    if (!LocationManagerCompat.isLocationEnabled(manager)) return LocationResult.Unavailable
    return try {
        recentLastKnown(manager)?.let { return LocationResult.Found(it.toGeoPoint()) }
        val provider = providerFor(manager) ?: return LocationResult.Unavailable
        val location = withTimeoutOrNull(LOCATION_FIX_TIMEOUT_MS) { freshLocation(manager, provider) }
            ?: return LocationResult.TimedOut
        location.value?.let { LocationResult.Found(it.toGeoPoint()) } ?: LocationResult.Unavailable
    } catch (_: SecurityException) {
        LocationResult.Denied
    }
}

/**
 * The network provider is the coarse one. From Android 12 a coarse grant also covers the fused and GPS providers,
 * which then report an approximate position.
 */
private fun providerFor(manager: LocationManager): String? {
    val candidates = buildList {
        add(LocationManager.NETWORK_PROVIDER)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            add(LocationManager.FUSED_PROVIDER)
            add(LocationManager.GPS_PROVIDER)
        }
    }
    return candidates.firstOrNull { it in manager.allProviders && manager.isProviderEnabled(it) }
}

@Suppress("MissingPermission") // checked by the caller; a revoked grant throws SecurityException
private fun recentLastKnown(manager: LocationManager): Location? = manager.getProviders(true)
    .mapNotNull { manager.getLastKnownLocation(it) }
    .filter { ageMillis(it) <= LOCATION_MAX_AGE_MS }
    .maxByOrNull { it.elapsedRealtimeNanos }

private fun ageMillis(location: Location): Long = (SystemClock.elapsedRealtimeNanos() - location.elapsedRealtimeNanos) / 1_000_000

/** Wraps the nullable fix so a null position is distinguishable from a timeout. */
private class Fix(val value: Location?)

@Suppress("MissingPermission")
private suspend fun freshLocation(manager: LocationManager, provider: String): Fix = suspendCancellableCoroutine { cont ->
    val signal = CancellationSignal()
    cont.invokeOnCancellation { signal.cancel() }
    LocationManagerCompat.getCurrentLocation(manager, provider, signal, Runnable::run) { location ->
        if (cont.isActive) cont.resume(Fix(location))
    }
}

private fun Location.toGeoPoint() = GeoPoint(latitude, longitude)
