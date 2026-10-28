@file:Suppress("UNUSED_PARAMETER")

package app.lagar.i18n

import androidx.compose.runtime.Composable

private fun readNavigatorLanguage(): String = js("window.__lagarSystemLanguage || (window.__lagarSystemLanguage = navigator.language)")

private fun overrideNavigatorLanguage(tag: String) {
    js("Object.defineProperty(navigator, 'language', { get: function () { return tag; }, configurable: true }); Object.defineProperty(navigator, 'languages', { get: function () { return [tag]; }, configurable: true })")
}

actual fun systemLanguageTag(): String = readNavigatorLanguage()

@Composable
internal actual fun ProvidePlatformLocale(tag: String, content: @Composable () -> Unit) {
    readNavigatorLanguage() // remember the real value before overriding
    overrideNavigatorLanguage(tag)
    content()
}
