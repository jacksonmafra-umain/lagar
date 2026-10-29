package app.lagar.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.SearchService
import app.lagar.domain.LoadState
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.SearchHit
import app.lagar.domain.SearchQuery
import app.lagar.domain.localityCode
import app.lagar.settings.UserPreferences
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch

/**
 * Search of the active scope through the [SearchService] (static index, or the catalog when the API has none).
 * [update] is debounced; the first query (from the route) runs at once, and so does a change of sort only. Region
 * and Kommun search the chosen län or kommun. A query with no text and no filter, and a Region or Kommun scope
 * without its locality, resolve to an empty result without downloading anything, so data is only fetched once the
 * user actually searches.
 */
class SearchViewModel(
    private val service: SearchService,
    preferences: UserPreferences,
    initial: SearchQuery = SearchQuery(""),
) : ViewModel() {
    private val _query = MutableStateFlow(initial)
    val query: StateFlow<SearchQuery> = _query.asStateFlow()

    private val _results = MutableStateFlow<LoadState<List<SearchHit>>>(LoadState.Loading)
    val results: StateFlow<LoadState<List<SearchHit>>> = _results.asStateFlow()

    private val attempt = MutableStateFlow(0)

    init {
        viewModelScope.launch {
            var previous = initial

            @OptIn(FlowPreview::class)
            val debounced = _query.debounce {
                val sortOnly = it == previous.copy(sort = it.sort)
                previous = it
                if (it === initial || sortOnly) 0 else DEBOUNCE_MS
            }
            combine(debounced, preferences.scope, preferences.locality, attempt) { query, scope, locality, _ ->
                Triple(query, scope, locality)
            }.collectLatest { (query, scope, locality) -> run(query, scope, locality) }
        }
    }

    fun update(query: SearchQuery) {
        _query.value = query
    }

    private suspend fun run(query: SearchQuery, scope: Scope, locality: Locality) {
        if (!query.isActive || (scope != Scope.Nationell && scope.localityCode(locality) == null)) {
            _results.value = LoadState.Loaded(emptyList())
            return
        }
        // The first search downloads the document table (or the whole catalog); show progress rather than stale results.
        if (_results.value !is LoadState.Loaded || !service.isWarm(scope)) _results.value = LoadState.Loading
        _results.value = try {
            LoadState.Loaded(service.search(query, scope, locality))
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            LoadState.Failed(retry = { attempt.value++ })
        }
    }

    private companion object {
        const val DEBOUNCE_MS = 250L
    }
}
