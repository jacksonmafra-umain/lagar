package app.lagar.ui.tjanster

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.GeoRepository
import app.lagar.data.ServiceRepository
import app.lagar.domain.LoadState
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.settings.UserPreferences
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/**
 * Loads the service catalogue and lists it for the user's chosen län and kommun (see [serviceEntries]); it lists
 * again when the choice changes. The catalogue is read once per process by the repository, so a change of
 * locality costs no request. A failed read is retried with [LoadState.Failed.retry].
 */
class TjansterViewModel(
    private val services: ServiceRepository,
    private val preferences: UserPreferences,
    private val geo: GeoRepository,
) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<List<ServiceEntry>>>(LoadState.Loading)
    val state: StateFlow<LoadState<List<ServiceEntry>>> = _state.asStateFlow()

    private val attempt = MutableStateFlow(0)

    init {
        viewModelScope.launch {
            combine(preferences.locality, attempt) { locality, _ -> locality }.collectLatest(::load)
        }
    }

    private suspend fun load(locality: Locality) {
        _state.value = LoadState.Loading
        _state.value = try {
            val catalog = services.serviceCatalog()
            val chosen = ServiceLocality.of(
                locality,
                regionName = geo.localityName(Scope.Region, locality),
                kommunName = geo.localityName(Scope.Kommun, locality),
            )
            LoadState.Loaded(serviceEntries(catalog.services, chosen))
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            LoadState.Failed(retry = ::retry)
        }
    }

    private fun retry() {
        attempt.value++
    }
}
