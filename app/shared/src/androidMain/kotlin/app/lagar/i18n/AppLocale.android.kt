package app.lagar.i18n

import android.content.res.Configuration
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalConfiguration
import java.util.Locale

// Captured on first use, before any override is applied; ProvidePlatformLocale touches it first.
private val systemLocale: Locale = Locale.getDefault()

actual fun systemLanguageTag(): String = systemLocale.toLanguageTag()

@Composable
internal actual fun ProvidePlatformLocale(tag: String, content: @Composable () -> Unit) {
    systemLocale // initialise before overriding the default
    val locale = Locale.forLanguageTag(tag)
    Locale.setDefault(locale)
    val configuration = Configuration(LocalConfiguration.current).apply { setLocale(locale) }
    CompositionLocalProvider(LocalConfiguration provides configuration, content = content)
}
