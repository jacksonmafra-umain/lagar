package app.lagar.ui.hierarki

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.ApiIndex
import app.lagar.data.LagarRepository
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.count
import app.lagar.domain.otherStatuteCount
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
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

/** Loads the API index once and exposes one summary per [DisplayLayer], in hierarchy order. */
class HierarkiViewModel(private val repository: LagarRepository) : ViewModel() {
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
                LoadState.Loaded(repository.index().layerSummaries())
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                LoadState.Failed(retry = ::load)
            }
        }
    }
}
