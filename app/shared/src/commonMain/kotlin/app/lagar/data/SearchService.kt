package app.lagar.data

import app.lagar.domain.DisplayLayer
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.SearchHit
import app.lagar.domain.SearchQuery
import app.lagar.domain.coversLocality
import app.lagar.domain.fieldMask
import app.lagar.domain.passes
import app.lagar.domain.queryTerms
import app.lagar.domain.searchHits
import app.lagar.domain.sortedFor
import kotlinx.datetime.LocalDate
import kotlinx.datetime.TimeZone
import kotlinx.datetime.todayIn
import kotlin.time.Clock

/**
 * Runs a [SearchQuery] for a scope; Region and Kommun are narrowed to the chosen län or kommun. Uses the static search index when the API has one ([index] non-null and its
 * manifest present), so only `docs.json` and the shards of the query terms are downloaded; otherwise falls back
 * to the [catalog] (every listing page of the scope) and substring matching over titles and numbers.
 *
 * `docs.json` has no `in_force` column yet, so an in-force filter on the index path reads the dates from the
 * catalog; once the API adds the column it is used directly.
 */
class SearchService(
    private val index: FullTextIndex?,
    private val catalog: Catalog,
    private val today: () -> LocalDate = { Clock.System.todayIn(TimeZone.currentSystemDefault()) },
) {
    /** Whether a search of [scope] can answer without a large download. */
    fun isWarm(scope: Scope): Boolean = index?.isWarm() == true || catalog.isLoaded(scope)

    /**
     * Matching documents of [scope], in [SearchQuery.sort] order. For Region and Kommun only documents of the
     * [locality]'s län or kommun match, so nothing does while it is unset.
     */
    suspend fun search(query: SearchQuery, scope: Scope, locality: Locality = Locality(null, null)): List<SearchHit> {
        if (!query.isValidRange || !query.isActive) return emptyList()
        val hits = index?.manifest()?.let { searchIndex(index, query, scope, locality) }
            ?: catalog.items(scope).filter { it.inScope(scope, locality) }.searchHits(query, today())
        return hits.distinctBy { it.item.id }.sortedFor(query.sort)
    }

    private suspend fun searchIndex(index: FullTextIndex, query: SearchQuery, scope: Scope, locality: Locality): List<SearchHit> {
        val terms = queryTerms(query.text)
        // Text made only of dropped words (stop words, single letters) matches nothing rather than everything.
        if (terms.isEmpty() && query.text.isNotBlank()) return emptyList()
        val docs = index.docs()
        val matches = if (terms.isEmpty()) null else index.match(terms, query.mode.fieldMask)
        val inForce = if (query.usesInForce && docs.none { it.inForce != null }) {
            catalog.items(scope).associate { it.id to it.inForce }
        } else {
            null
        }
        val today = today()
        val candidates = matches?.keys?.sorted() ?: docs.indices
        return candidates.mapNotNull { n ->
            val doc = docs.getOrNull(n) ?: return@mapNotNull null
            val item = if (inForce != null) doc.copy(inForce = inForce[doc.id]) else doc
            if (!item.inScope(scope, locality) || !item.passes(query, today)) return@mapNotNull null
            val match = matches?.get(n)
            SearchHit(item, match?.any ?: 0, match?.all ?: 0)
        }
    }
}

/** Whether a document of this type belongs to [scope] and its [locality]; `other_statute` is national. */
internal fun ListingItem.inScope(scope: Scope, locality: Locality): Boolean {
    val level = DisplayLayer.forType(type)
    val inLevels = if (level == null) scope == Scope.Nationell else level in scope.layers
    return inLevels && scope.coversLocality(this, locality)
}
