package app.lagar.i18n

import androidx.compose.runtime.Composable
import platform.Foundation.NSLocale
import platform.Foundation.NSUserDefaults
import platform.Foundation.preferredLanguages

private const val APPLE_LANGUAGES = "AppleLanguages"

// The system value lives in NSGlobalDomain; the app domain holds our override, so reading the
// global domain keeps `System` correct after a restart with a persisted override.
actual fun systemLanguageTag(): String {
    val global = NSUserDefaults.standardUserDefaults.persistentDomainForName("NSGlobalDomain")
    val languages = global?.get(APPLE_LANGUAGES) as? List<*>
    return (languages?.firstOrNull() as? String)
        ?: (NSLocale.preferredLanguages.firstOrNull() as? String)
        ?: "sv"
}

@Composable
internal actual fun ProvidePlatformLocale(tag: String, content: @Composable () -> Unit) {
    NSUserDefaults.standardUserDefaults.setObject(listOf(tag), APPLE_LANGUAGES)
    content()
}
