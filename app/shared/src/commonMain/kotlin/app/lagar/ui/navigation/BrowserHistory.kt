package app.lagar.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavController
import androidx.navigation.NavHostController

/** Web only: keeps the address bar and the browser's back and forward in step with the back stack; no-op elsewhere. */
@Composable
internal expect fun BrowserHistoryEffect(navController: NavHostController)

/**
 * Navigates through [stack], the route strings the browser history keeps for a page (one per back stack entry, as
 * `bindToBrowserNavigation` writes them), on top of the current entry. Stops at the first route the graph does not
 * know, such as one saved by an older version of the app. The splash and onboarding are skipped. Returns whether any
 * route applied.
 */
fun NavController.restoreStack(stack: List<String>): Boolean {
    var restored = false
    for (route in stack) {
        if (route.substringBefore('/').substringBefore('?') in TRANSIENT) continue
        try {
            navigate(route) { launchSingleTop = true }
        } catch (_: IllegalArgumentException) {
            break
        }
        restored = true
    }
    return restored
}

// The serial names that start the route strings of the screens never restored.
private val TRANSIENT = setOf(Splash.serializer(), OnboardingWelcome.serializer(), OnboardingScope.serializer())
    .map { it.descriptor.serialName }
    .toSet()
