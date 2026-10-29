package app.lagar.ui.onboarding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.LagarRepository
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.count
import app.lagar.domain.hasLocality
import app.lagar.domain.withRegion
import app.lagar.settings.UserFocus
import app.lagar.settings.UserPreferences
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** The user's choices while onboarding. Nothing reaches [UserPreferences] until [finish] or [skip]. */
class OnboardingViewModel(
    private val repository: LagarRepository,
    private val preferences: UserPreferences,
) : ViewModel() {
    private val _scope = MutableStateFlow(Scope.Nationell)
    val scope: StateFlow<Scope> = _scope.asStateFlow()

    private val _locality = MutableStateFlow(Locality(null, null))
    val locality: StateFlow<Locality> = _locality.asStateFlow()

    private val _focus = MutableStateFlow(preferences.focus.value)
    val focus: StateFlow<UserFocus> = _focus.asStateFlow()

    /** Documents per scope; null while the index is loading or when it could not be loaded. */
    private val _counts = MutableStateFlow<Map<Scope, Int>?>(null)
    val counts: StateFlow<Map<Scope, Int>?> = _counts.asStateFlow()

    init {
        viewModelScope.launch {
            try {
                val index = repository.index()
                _counts.value = Scope.entries.associateWith { index.count(it) }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // Counts are decoration here; the badges stay hidden and Home reports the failure.
            }
        }
    }

    fun selectScope(scope: Scope) {
        _scope.value = scope
    }

    fun selectFocus(focus: UserFocus) {
        _focus.value = focus
    }

    fun selectRegion(code: String?) {
        _locality.update { it.withRegion(code) }
    }

    fun selectKommun(code: String?) {
        _locality.update { it.copy(kommunCode = code) }
    }

    fun finish() = preferences.completeOnboarding(_scope.value, _locality.value, _focus.value)

    /**
     * Leaves onboarding from any step without throwing away what was picked: the focus and any län or kommun are kept,
     * and so is the scope when it has the locality it needs. A Region or Kommun scope still missing its place falls
     * back to Nationell, so Home never opens on a scope with nothing to show.
     */
    fun skip() {
        val locality = _locality.value
        val scope = _scope.value.takeIf { it.hasLocality(locality) } ?: Scope.Nationell
        preferences.completeOnboarding(scope, locality, _focus.value)
    }
}
