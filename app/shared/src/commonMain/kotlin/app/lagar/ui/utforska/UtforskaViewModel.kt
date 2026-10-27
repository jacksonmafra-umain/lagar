package app.lagar.ui.utforska

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.LagarRepository
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.count
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class LayerSummary(val layer: DisplayLayer, val count: Int)

/** Loads the API index once and exposes one summary per [DisplayLayer], in hierarchy order. */
class UtforskaViewModel(private val repository: LagarRepository) : ViewModel() {
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
                val index = repository.index()
                LoadState.Loaded(DisplayLayer.entries.map { LayerSummary(it, index.count(it)) })
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                LoadState.Failed(retry = ::load)
            }
        }
    }
}
