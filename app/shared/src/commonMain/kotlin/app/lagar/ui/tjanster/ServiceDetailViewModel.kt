package app.lagar.ui.tjanster

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.GeoRepository
import app.lagar.data.LagarRepository
import app.lagar.data.ServiceRepository
import app.lagar.data.ServiceSummary
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import app.lagar.settings.UserPreferences
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Loads one service ([id], `service-<slug>`): its catalogue entry, which carries the issuer, channels and the norms
 * it is based on, and its document, which carries the lead paragraph and the fetch date. A service the catalogue
 * does not list, or any failed read, becomes [LoadState.Failed] whose retry loads both again. The place is worked out
 * for the län and kommun chosen when the screen opens, so a kommun template links to that kommun's website.
 */
class ServiceDetailViewModel(
    private val services: ServiceRepository,
    private val documents: LagarRepository,
    private val preferences: UserPreferences,
    private val geo: GeoRepository,
    private val id: String,
) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<ServiceDetail>>(LoadState.Loading)
    val state: StateFlow<LoadState<ServiceDetail>> = _state.asStateFlow()

    private var job: Job? = null

    init {
        load()
    }

    private fun load() {
        job?.cancel()
        _state.value = LoadState.Loading
        job = viewModelScope.launch {
            _state.value = try {
                coroutineScope {
                    val document = async { documents.document(id) }
                    val service = services.serviceCatalog().services.firstOrNull { it.id == id }
                        ?: error("service $id is not in the catalogue")
                    val response = document.await()
                    LoadState.Loaded(
                        ServiceDetail(service, serviceLead(response.body), fetchDate(response.meta.fetchedAt), place(service)),
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                LoadState.Failed(retry = ::load)
            }
        }
    }

    private suspend fun place(service: ServiceSummary): ServicePlace? {
        val locality = preferences.locality.value
        val chosen = ServiceLocality.of(
            locality,
            regionName = geo.localityName(Scope.Region, locality),
            kommunName = geo.localityName(Scope.Kommun, locality),
            kommunWebsite = geo.kommunWebsite(locality),
        )
        return serviceEntries(listOf(service), chosen).firstOrNull()?.place
    }
}
