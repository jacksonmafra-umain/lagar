package app.lagar.ui.reader

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.Catalog
import app.lagar.data.DocumentResponse
import app.lagar.data.LagarRepository
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Loads one document; a failure becomes [LoadState.Failed] whose retry reloads it. [linkedAmendments]
 * holds the amending SFS numbers that the API also publishes as documents, so the reader can link them.
 */
class ReaderViewModel(
    private val repository: LagarRepository,
    private val catalog: Catalog,
    private val id: String,
) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<DocumentResponse>>(LoadState.Loading)
    val state: StateFlow<LoadState<DocumentResponse>> = _state.asStateFlow()

    private val _linkedAmendments = MutableStateFlow<Map<String, String>>(emptyMap())

    /** Amending SFS number to the id of its document, for the numbers whose document exists. */
    val linkedAmendments: StateFlow<Map<String, String>> = _linkedAmendments.asStateFlow()

    private var job: Job? = null
    private var linkJob: Job? = null

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

    /**
     * Looks up which of [numbers] the API has as documents, through the national catalog (shared with
     * search, so it is loaded at most once per process). Runs once; on failure the numbers stay plain text
     * and the next call tries again.
     */
    fun resolveAmendmentLinks(numbers: List<String>) {
        if (linkJob?.isActive == true || _linkedAmendments.value.isNotEmpty()) return
        val candidates = numbers.mapNotNull { number -> sfsDocumentId(number)?.takeIf { it != id }?.let { number to it } }
        if (candidates.isEmpty()) return
        linkJob = viewModelScope.launch {
            try {
                val known = catalog.items(Scope.Nationell).mapTo(HashSet()) { it.id }
                _linkedAmendments.value = candidates.filter { it.second in known }.toMap()
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
            }
        }
    }
}
