package app.lagar.ui.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.ApiLayer
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
 *
 * The layer's entry in `index.json` gives the [series] to switch between and lets a layer or series
 * the index lists as empty load as an empty page without a request. If the index cannot be read, the
 * listing still loads and the switch stays hidden.
 */
class LayerListViewModel(
    private val repository: LagarRepository,
    private val layer: String,
    type: String?,
) : ViewModel() {
    private val _selectedType = MutableStateFlow(type)

    /** The series being listed; `null` lists the whole layer. */
    val selectedType: StateFlow<String?> = _selectedType.asStateFlow()

    private val _series = MutableStateFlow<List<String>>(emptyList())

    /** The layer's series in index order when there are at least two to switch between; empty otherwise. */
    val series: StateFlow<List<String>> = _series.asStateFlow()

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
    private var indexRead = false
    private var indexLayer: ApiLayer? = null

    init {
        loadFirst()
    }

    private fun loadFirst() {
        job?.cancel()
        _state.value = LoadState.Loading
        job = viewModelScope.launch {
            try {
                readIndex()
                val type = _selectedType.value
                if (indexRead && !indexLists(type)) {
                    _items.value = emptyList()
                    _total.value = 0
                    pageCount = 1
                    loadedPages = 1
                    _state.value = LoadState.Loaded(Unit)
                    return@launch
                }
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
                val page = repository.listing(layer, _selectedType.value, loadedPages + 1)
                // Ids are LazyColumn keys; a repeated id (a page boundary overlap) would crash the list.
                _items.value = (_items.value + page.items).distinctBy { it.id }
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

    /** Lists [type] instead (`null` for the whole layer), from its first page. */
    fun selectSeries(type: String?) {
        if (type == _selectedType.value) return
        _selectedType.value = type
        _items.value = emptyList()
        _total.value = null
        _appending.value = false
        _appendFailed.value = false
        loadedPages = 0
        pageCount = 1
        loadFirst()
    }

    /** Reads the layer's index entry once; a failure leaves it unknown and is retried on the next first load. */
    private suspend fun readIndex() {
        if (indexRead) return
        try {
            indexLayer = repository.index().layers.firstOrNull { it.id == layer }
            indexRead = true
            _series.value = indexLayer?.series?.map { it.id }?.takeIf { it.size > 1 }.orEmpty()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            // The listing does not depend on the index.
        }
    }

    /** Whether the index lists documents for [type] (or for the layer when `null`). */
    private fun indexLists(type: String?): Boolean {
        val entry = indexLayer ?: return false
        return if (type == null) entry.count > 0 else entry.series.any { it.id == type && it.count > 0 }
    }

    /** Retries the page that failed in [loadNext]. */
    fun retryNext() {
        _appendFailed.value = false
        loadNext()
    }
}
