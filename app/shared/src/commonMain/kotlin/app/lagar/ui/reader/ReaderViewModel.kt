package app.lagar.ui.reader

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.domain.LoadState
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Loads one document; a failure becomes [LoadState.Failed] whose retry reloads it. */
class ReaderViewModel(private val repository: LagarRepository, private val id: String) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<DocumentResponse>>(LoadState.Loading)
    val state: StateFlow<LoadState<DocumentResponse>> = _state.asStateFlow()

    private var job: Job? = null

    init {
        load()
    }

    private fun load() {
        job?.cancel()
        _state.value = LoadState.Loading
        job = viewModelScope.launch {
            _state.value = try {
                LoadState.Loaded(repository.document(id))
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                LoadState.Failed(retry = ::load)
            }
        }
    }
}
