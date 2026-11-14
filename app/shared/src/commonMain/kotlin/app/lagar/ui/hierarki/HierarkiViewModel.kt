package app.lagar.ui.hierarki

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.ApiIndex
import app.lagar.data.LagarRepository
import app.lagar.data.ServiceRepository
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.count
import app.lagar.domain.otherStatuteCount
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** The documents of one level; [otherStatutes] are the SFS other statutes already included in [count]. */
data class LayerSummary(val layer: DisplayLayer, val count: Int, val otherStatutes: Int = 0)

/** One summary per [DisplayLayer], in hierarchy order; the SFS acts carry the other statutes they include. */
fun ApiIndex.layerSummaries(): List<LayerSummary> = DisplayLayer.entries.map {
    LayerSummary(it, count(it), if (it.groupedTypes.isEmpty()) 0 else otherStatuteCount())
}

/** These summaries with the service level counting the [total] of the service catalogue. */
fun List<LayerSummary>.withServiceCount(total: Int): List<LayerSummary> =
    map { if (it.layer == DisplayLayer.Service) it.copy(count = total) else it }

/**
 * Loads the API index and the service catalogue once and exposes one summary per [DisplayLayer], in hierarchy order.
 * The service level shows the catalogue's total, the count the Tjänster tab lists; when only the catalogue fails to
 * load, it keeps the index count rather than failing the whole screen.
 */
class HierarkiViewModel(private val repository: LagarRepository, private val services: ServiceRepository) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<List<LayerSummary>>>(LoadState.Loading)
    val state: StateFlow<LoadState<List<LayerSummary>>> = _state.asStateFlow()

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
                    val catalogue = async { serviceTotal() }
                    val summaries = repository.index().layerSummaries()
                    LoadState.Loaded(catalogue.await()?.let { summaries.withServiceCount(it) } ?: summaries)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                LoadState.Failed(retry = ::load)
            }
        }
    }

    private suspend fun serviceTotal(): Int? = try {
        services.serviceCatalog().total
    } catch (e: CancellationException) {
        throw e
    } catch (_: Exception) {
        null
    }
}
