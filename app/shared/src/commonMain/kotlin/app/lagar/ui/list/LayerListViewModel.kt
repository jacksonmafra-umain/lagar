package app.lagar.ui.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.domain.LoadState
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Pages through one layer's listing, in the order the API returns it. [state] covers the first page
 * (a failure there replaces the screen); later pages report through [appending] and [appendFailed]
 * so the loaded items stay on screen.
 */
class LayerListViewModel(
    private val repository: LagarRepository,
    private val layer: String,
    private val type: String?,
) : ViewModel() {
    private val _items = MutableStateFlow<List<ListingItem>>(emptyList())
    val items: StateFlow<List<ListingItem>> = _items.asStateFlow()

    private val _total = MutableStateFlow<Int?>(null)
    val total: StateFlow<Int?> = _total.asStateFlow()

    private val _state = MutableStateFlow<LoadState<Unit>>(LoadState.Loading)
    val state: StateFlow<LoadState<Unit>> = _state.asStateFlow()

    private val _appending = MutableStateFlow(false)
    val appending: StateFlow<Boolean> = _appending.asStateFlow()

    private val _appendFailed = MutableStateFlow(false)
    val appendFailed: StateFlow<Boolean> = _appendFailed.asStateFlow()

    private var loadedPages = 0
    private var pageCount = 1
    private var job: Job? = null

    init {
        loadFirst()
    }

    private fun loadFirst() {
        job?.cancel()
        _state.value = LoadState.Loading
        job = viewModelScope.launch {
            try {
                val page = repository.listing(layer, type, 1)
                _items.value = page.items
                _total.value = page.total
                pageCount = page.pageCount
                loadedPages = 1
                _state.value = LoadState.Loaded(Unit)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                _state.value = LoadState.Failed(retry = ::loadFirst)
            }
        }
    }

    /** Loads the next page; does nothing while one is loading, after a failed one, or at the last page. */
    fun loadNext() {
        if (_state.value !is LoadState.Loaded || _appending.value || _appendFailed.value || loadedPages >= pageCount) return
        _appending.value = true
        job = viewModelScope.launch {
            try {
                val page = repository.listing(layer, type, loadedPages + 1)
                _items.value += page.items
                loadedPages = page.page
                pageCount = page.pageCount
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                _appendFailed.value = true
            } finally {
                _appending.value = false
            }
        }
    }

    /** Retries the page that failed in [loadNext]. */
    fun retryNext() {
        _appendFailed.value = false
        loadNext()
    }
}
