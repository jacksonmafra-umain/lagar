package app.lagar.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.Catalog
import app.lagar.data.ListingItem
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import app.lagar.domain.SearchQuery
import app.lagar.domain.search
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
 * Client-side search over the [Catalog] of the active scope. [update] is debounced; the first query
 * (from the route) runs at once. A query with no text and no filter, and any scope other than
 * Nationell (no documents yet), resolve to an empty result without touching the catalog.
 */
class SearchViewModel(
    private val catalog: Catalog,
    preferences: UserPreferences,
    initial: SearchQuery = SearchQuery(""),
) : ViewModel() {
    private val _query = MutableStateFlow(initial)
    val query: StateFlow<SearchQuery> = _query.asStateFlow()

    private val _results = MutableStateFlow<LoadState<List<ListingItem>>>(LoadState.Loading)
    val results: StateFlow<LoadState<List<ListingItem>>> = _results.asStateFlow()

    private val attempt = MutableStateFlow(0)

    init {
        viewModelScope.launch {
            @OptIn(FlowPreview::class)
            val debounced = _query.debounce { if (it === initial) 0 else DEBOUNCE_MS }
            combine(debounced, preferences.scope, attempt) { query, scope, _ -> query to scope }
                .collectLatest { (query, scope) -> run(query, scope) }
        }
    }

    fun update(query: SearchQuery) {
        _query.value = query
    }

    private suspend fun run(query: SearchQuery, scope: Scope) {
        if (scope != Scope.Nationell || !query.isActive) {
            _results.value = LoadState.Loaded(emptyList())
            return
        }
        if (_results.value !is LoadState.Loaded) _results.value = LoadState.Loading
        _results.value = try {
            LoadState.Loaded(catalog.items(scope).search(query).distinctBy { it.id })
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
