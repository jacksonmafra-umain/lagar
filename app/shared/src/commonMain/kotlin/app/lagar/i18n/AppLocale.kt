package app.lagar.i18n

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.key

/** BCP 47 tag of the device language, unaffected by the in-app override. */
expect fun systemLanguageTag(): String

/**
 * Makes the platform's resource locale equal [tag] for the duration of the composition.
 * Implementations must be safe to call repeatedly with changing tags.
 */
@Composable
internal expect fun ProvidePlatformLocale(tag: String, content: @Composable () -> Unit)

/**
 * Forces string resources to [language] and recomposes [content] when it changes, so the
 * language can be switched at runtime without restarting. Needed because `values/` is English
 * while the default for unsupported system locales is Swedish.
 */
@Composable
fun ProvideAppLocale(language: SupportedLanguage, content: @Composable () -> Unit) {
    key(language) {
        CompositionLocalProvider(LocalAppLanguage provides language) {
            ProvidePlatformLocale(language.tag, content)
        }
    }
}
