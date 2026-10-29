package app.lagar.settings

import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.withRegion
import app.lagar.i18n.LanguageChoice
import com.russhwolf.settings.Settings
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Device-local user settings; unknown or missing stored values fall back to `System`. */
class UserPreferences(private val settings: Settings) {
    private val _language = MutableStateFlow(read(KEY_LANGUAGE, LanguageChoice.System))
    private val _theme = MutableStateFlow(read(KEY_THEME, ThemeMode.System))
    private val _reduceTransparency = MutableStateFlow(read(KEY_REDUCE_TRANSPARENCY, ReduceTransparency.System))

    private val _onboardingDone = MutableStateFlow(settings.getBoolean(KEY_ONBOARDING_DONE, false))
    private val _scope = MutableStateFlow(read(KEY_SCOPE, Scope.Nationell))
    private val _locality = MutableStateFlow(
        Locality(settings.getStringOrNull(KEY_REGION), settings.getStringOrNull(KEY_KOMMUN)),
    )

    val language: StateFlow<LanguageChoice> = _language.asStateFlow()
    val theme: StateFlow<ThemeMode> = _theme.asStateFlow()
    val reduceTransparency: StateFlow<ReduceTransparency> = _reduceTransparency.asStateFlow()

    val onboardingDone: StateFlow<Boolean> = _onboardingDone.asStateFlow()
    val scope: StateFlow<Scope> = _scope.asStateFlow()
    val locality: StateFlow<Locality> = _locality.asStateFlow()

    fun completeOnboarding(scope: Scope, locality: Locality) {
        setScope(scope)
        writeLocality(locality)
        settings.putBoolean(KEY_ONBOARDING_DONE, true)
        _onboardingDone.value = true
    }

    fun setScope(scope: Scope) {
        settings.putString(KEY_SCOPE, scope.name)
        _scope.value = scope
    }

    fun setLocality(locality: Locality) = writeLocality(locality)

    fun setRegion(code: String?) = writeLocality(_locality.value.withRegion(code))

    fun setKommun(code: String?) = writeLocality(_locality.value.copy(kommunCode = code))

    private fun writeLocality(locality: Locality) {
        putOrRemove(KEY_REGION, locality.regionCode)
        putOrRemove(KEY_KOMMUN, locality.kommunCode)
        _locality.value = locality
    }

    private fun putOrRemove(key: String, value: String?) {
        if (value == null) settings.remove(key) else settings.putString(key, value)
    }

    fun setLanguage(choice: LanguageChoice) {
        settings.putString(KEY_LANGUAGE, choice.name)
        _language.value = choice
    }

    fun setTheme(mode: ThemeMode) {
        settings.putString(KEY_THEME, mode.name)
        _theme.value = mode
    }

    fun setReduceTransparency(choice: ReduceTransparency) {
        settings.putString(KEY_REDUCE_TRANSPARENCY, choice.name)
        _reduceTransparency.value = choice
    }

    private inline fun <reified E : Enum<E>> read(key: String, default: E): E {
        val stored = settings.getStringOrNull(key) ?: return default
        return enumValues<E>().firstOrNull { it.name == stored } ?: default
    }

    private companion object {
        const val KEY_LANGUAGE = "language"
        const val KEY_THEME = "theme"
        const val KEY_REDUCE_TRANSPARENCY = "reduce_transparency"
        const val KEY_ONBOARDING_DONE = "onboarding_done"
        const val KEY_SCOPE = "scope"
        const val KEY_REGION = "region"
        const val KEY_KOMMUN = "kommun"
    }
}
