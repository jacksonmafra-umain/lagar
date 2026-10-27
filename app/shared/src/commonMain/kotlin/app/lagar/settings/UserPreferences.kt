package app.lagar.settings

import app.lagar.i18n.LanguageChoice
import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Device-local user settings; unknown or missing stored values fall back to `System`. */
class UserPreferences(private val settings: Settings) {
    private val _language = MutableStateFlow(read(KEY_LANGUAGE, LanguageChoice.System))
    private val _theme = MutableStateFlow(read(KEY_THEME, ThemeMode.System))

    val language: StateFlow<LanguageChoice> = _language.asStateFlow()
    val theme: StateFlow<ThemeMode> = _theme.asStateFlow()

    fun setLanguage(choice: LanguageChoice) {
        settings.putString(KEY_LANGUAGE, choice.name)
        _language.value = choice
    }

    fun setTheme(mode: ThemeMode) {
        settings.putString(KEY_THEME, mode.name)
        _theme.value = mode
    }

    private inline fun <reified E : Enum<E>> read(key: String, default: E): E {
        val stored = settings.getStringOrNull(key) ?: return default
        return enumValues<E>().firstOrNull { it.name == stored } ?: default
    }

    private companion object {
        const val KEY_LANGUAGE = "language"
        const val KEY_THEME = "theme"
    }
}
