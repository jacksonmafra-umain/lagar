package app.lagar.ui.hierarki

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.MinistryIndex
import app.lagar.data.MinistryRepository
import app.lagar.domain.LoadState
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Loads the per-ministry index of one SFS series ([layer], [type]) once, with a retry on failure. */
class MinistriesViewModel(
    private val repository: MinistryRepository,
    val layer: String,
    val type: String,
) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<MinistryIndex>>(LoadState.Loading)
    val state: StateFlow<LoadState<MinistryIndex>> = _state.asStateFlow()

    private var job: Job? = null

    init {
        load()
    }

    private fun load() {
        job?.cancel()
        _state.value = LoadState.Loading
        job = viewModelScope.launch {
            _state.value = try {
                LoadState.Loaded(repository.ministries(layer, type))
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                LoadState.Failed(retry = ::load)
            }
        }
    }
}
