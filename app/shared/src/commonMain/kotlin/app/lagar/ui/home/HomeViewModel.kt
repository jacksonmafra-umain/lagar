package app.lagar.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.lagar.data.GeoRepository
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.count
import app.lagar.settings.Bookmark
import app.lagar.settings.BookmarkStore
import app.lagar.settings.UserPreferences
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch

/**
 * What the home of one [scope] shows. [localityName] is the chosen län (Region) or kommun (Kommun), null when unset.
 * [layers] are the scope's levels that have documents, in hierarchy order.
 */
data class HomeData(
    val scope: Scope,
    val localityName: String?,
    val layers: List<DisplayLayer>,
    val fundamental: List<ListingItem>,
    val acts: List<ListingItem>,
    val ordinances: List<ListingItem>,
    val recent: List<ListingItem>,
    val hasMoreRecent: Boolean,
)

/**
 * Loads the home of the active scope and reloads when the scope or the locality changes. Only the first
 * listing pages it shows are fetched; the full catalog is left to search.
 */
class HomeViewModel(
    private val repository: LagarRepository,
    private val preferences: UserPreferences,
    private val bookmarkStore: BookmarkStore,
    private val geo: GeoRepository,
) : ViewModel() {
    private val _state = MutableStateFlow<LoadState<HomeData>>(LoadState.Loading)
    val state: StateFlow<LoadState<HomeData>> = _state.asStateFlow()

    val bookmarks: StateFlow<List<Bookmark>> = bookmarkStore.bookmarks

    private val attempt = MutableStateFlow(0)

    init {
        viewModelScope.launch {
            combine(preferences.scope, preferences.locality, attempt) { scope, locality, _ -> scope to locality }
                .collectLatest { (scope, locality) -> load(scope, locality) }
        }
    }

    private suspend fun load(scope: Scope, locality: Locality) {
        _state.value = LoadState.Loading
        _state.value = try {
            LoadState.Loaded(build(scope, locality))
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            LoadState.Failed(retry = { attempt.value++ })
        }
    }

    private suspend fun build(scope: Scope, locality: Locality): HomeData {
        val localityName = geo.localityName(scope, locality)
        // Only the national level has documents so far; Region and Kommun make no listing requests.
        if (scope != Scope.Nationell) return HomeData(scope, localityName, emptyList(), emptyList(), emptyList(), emptyList(), emptyList(), false)
        val index = repository.index()
        val feed = loadHomeFeed(repository, index, scope, IMPORTANT_LIMIT, RECENT_LIMIT)
        return HomeData(
            scope = scope,
            localityName = localityName,
            layers = scope.layers.filter { index.count(it) > 0 },
            fundamental = feed.fundamental,
            acts = feed.acts,
            ordinances = feed.ordinances,
            recent = feed.recent,
            hasMoreRecent = feed.hasMoreRecent,
        )
    }

    fun toggleBookmark(item: ListingItem) {
        val layer = item.displayLayer()?.apiLayer ?: DisplayLayer.SfsAct.apiLayer
        bookmarkStore.toggle(Bookmark(item.id, item.title, item.number, item.type, layer, item.issued, item.repealed))
    }

    private companion object {
        const val IMPORTANT_LIMIT = 5
        const val RECENT_LIMIT = 20
    }
}

/** The display level of a listing item, from its API `type`; null for types the home does not group yet. */
internal fun ListingItem.displayLayer(): DisplayLayer? = when (type) {
    "fundamental_law" -> DisplayLayer.Fundamental
    "act" -> DisplayLayer.SfsAct
    "ordinance" -> DisplayLayer.SfsOrdinance
    else -> null
}
