package app.lagar.ui.home

import app.lagar.data.ApiException
import app.lagar.data.ApiIndex
import app.lagar.data.LagarRepository
import app.lagar.data.ListingItem
import app.lagar.data.LocalityRepository
import app.lagar.data.NewestFirst
import app.lagar.domain.DisplayLayer
import app.lagar.domain.Scope
import app.lagar.domain.count
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope

/** The document lists of a scope home; [hasMoreRecent] when the scope holds more than [recent] shows. */
internal data class HomeFeed(
    val fundamental: List<ListingItem>,
    val acts: List<ListingItem>,
    val ordinances: List<ListingItem>,
    val recent: List<ListingItem>,
    val hasMoreRecent: Boolean,
)

/**
 * Builds the home lists from the first listing page of each level that has documents, fetched in
 * parallel, and loads a later page only when the lists could still reach into it. Listings are sorted
 * newest first, so with 50-item pages and the limits below the first pages are enough; the result
 * equals what the whole catalog would give.
 */
internal suspend fun loadHomeFeed(
    repository: LagarRepository,
    index: ApiIndex,
    scope: Scope,
    importantLimit: Int,
    recentLimit: Int,
): HomeFeed {
    val levels = scope.layers.filter { index.count(it) > 0 }.map { LevelPages(it) }
    coroutineScope { levels.map { async { it.loadNext(repository) } }.awaitAll() }
    fun level(layer: DisplayLayer) = levels.firstOrNull { it.layer == layer }

    level(DisplayLayer.Fundamental)?.loadUntil(repository) { false }
    level(DisplayLayer.SfsAct)?.loadUntil(repository) { it.size >= importantLimit }
    level(DisplayLayer.SfsOrdinance)?.loadUntil(repository) { it.size >= importantLimit }

    var recent: List<ListingItem>
    while (true) {
        recent = levels.flatMap { it.items }.sortedWith(NewestFirst).take(recentLimit)
        // Unloaded items sort after a level's last loaded one, so they can only enter the top if that one did.
        val short = levels.filter { level -> level.hasMore && level.items.lastOrNull().let { last -> last == null || recent.any { it === last } } }
        if (short.isEmpty()) break
        short.forEach { it.loadNext(repository) }
    }

    fun of(layer: DisplayLayer) = level(layer)?.items.orEmpty().filter { it.displayLayer() == layer }
    return HomeFeed(
        fundamental = of(DisplayLayer.Fundamental),
        acts = of(DisplayLayer.SfsAct).take(importantLimit),
        ordinances = of(DisplayLayer.SfsOrdinance).take(importantLimit),
        recent = recent,
        hasMoreRecent = levels.sumOf { it.total } > recentLimit,
    )
}

/** The pages of one level loaded so far, in API order. */
private class LevelPages(val layer: DisplayLayer) {
    val items = mutableListOf<ListingItem>()
    var total = 0
        private set
    private var loaded = 0
    private var pageCount = 1

    val hasMore: Boolean get() = loaded < pageCount

    suspend fun loadNext(repository: LagarRepository) {
        val page = repository.listing(layer.apiLayer, layer.apiType, loaded + 1)
        items += page.items
        pageCount = page.pageCount
        total = page.total
        loaded++
    }

    suspend fun loadUntil(repository: LagarRepository, enough: (List<ListingItem>) -> Boolean) {
        while (hasMore && !enough(items)) loadNext(repository)
    }
}

/**
 * The lists of a Region or Kommun home for one län or kommun [code] of [layer]. [total] is the locality's document
 * count, [key] its newest regulations still in force, [recent] its newest documents.
 */
internal data class LocalityFeed(
    val total: Int,
    val key: List<ListingItem>,
    val recent: List<ListingItem>,
    val hasMoreRecent: Boolean,
) {
    companion object {
        val Empty = LocalityFeed(0, emptyList(), emptyList(), false)
    }
}

/**
 * Reads the per-locality index and, when it lists [code], that locality's listing: the first page, and later ones
 * only while fewer than [keyLimit] of the loaded documents are in force. A code the index does not list, and an
 * API built before the per-locality listings (no index), give [LocalityFeed.Empty] without further requests.
 */
internal suspend fun loadLocalityFeed(
    source: LocalityRepository,
    layer: DisplayLayer,
    code: String,
    keyLimit: Int,
    recentLimit: Int,
): LocalityFeed {
    val count = try {
        source.localities(layer.apiLayer).count(code)
    } catch (e: ApiException) {
        if (e.notFound) return LocalityFeed.Empty else throw e
    }
    if (count == 0) return LocalityFeed.Empty
    val items = mutableListOf<ListingItem>()
    var page = source.localityListing(layer.apiLayer, code, 1)
    items += page.items
    while (items.count { it.repealed == null } < keyLimit && page.page < page.pageCount) {
        page = source.localityListing(layer.apiLayer, code, page.page + 1)
        items += page.items
    }
    return LocalityFeed(
        total = page.total,
        key = items.filter { it.repealed == null }.take(keyLimit),
        recent = items.take(recentLimit),
        hasMoreRecent = page.total > recentLimit,
    )
}
