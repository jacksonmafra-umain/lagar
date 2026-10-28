package app.lagar.data

import app.lagar.domain.DisplayLayer
import app.lagar.domain.Scope
import app.lagar.domain.count
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
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

    /** The first page gives the page count; the rest are fetched a few at a time, kept in page order. */
    private suspend fun loadLayer(layer: DisplayLayer): List<ListingItem> {
        val first = repo.listing(layer.apiLayer, layer.apiType, 1)
        val rest = (2..first.pageCount).chunked(PARALLEL_PAGES).flatMap { pages ->
            coroutineScope { pages.map { async { repo.listing(layer.apiLayer, layer.apiType, it) } }.awaitAll() }
        }
        return first.items + rest.flatMap { it.items }
    }

    private companion object {
        const val PARALLEL_PAGES = 6
    }
}

/** Newest `issued` first, items without a date last; stable, so equal dates keep their listing order. */
internal val NewestFirst: Comparator<ListingItem> =
    compareByDescending<ListingItem> { it.issued != null }.thenByDescending { it.issued }
