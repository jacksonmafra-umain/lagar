package app.lagar.data

import app.lagar.domain.DisplayLayer
import app.lagar.domain.Scope
import app.lagar.domain.count
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Every listing item of a scope, loaded once per process for client-side search. Concurrent callers share
 * one load: the rest wait on the lock and then read the cache. Failures are not cached.
 */
class Catalog(private val repo: LagarRepository) {
    private val lock = Mutex()
    private val cache = mutableMapOf<Scope, List<ListingItem>>()

    /** Newest `issued` first; items without a date come last. */
    suspend fun items(scope: Scope): List<ListingItem> = lock.withLock {
        cache[scope] ?: load(scope).also { cache[scope] = it }
    }

    /** Whether [items] for [scope] would answer from the cache, without loading. */
    fun isLoaded(scope: Scope): Boolean = scope in cache

    private suspend fun load(scope: Scope): List<ListingItem> {
        val index = repo.index()
        val items = scope.layers.filter { index.count(it) > 0 }.flatMap { loadLayer(it) }
        return items.sortedWith(NewestFirst)
    }

    private suspend fun loadLayer(layer: DisplayLayer): List<ListingItem> {
        val items = mutableListOf<ListingItem>()
        var page = 1
        var pageCount = 1
        while (page <= pageCount) {
            val result = repo.listing(layer.apiLayer, layer.apiType, page)
            pageCount = result.pageCount
            items += result.items
            page++
        }
        return items
    }
}

/** Newest `issued` first, items without a date last; stable, so equal dates keep their listing order. */
internal val NewestFirst: Comparator<ListingItem> =
    compareByDescending<ListingItem> { it.issued != null }.thenByDescending { it.issued }
