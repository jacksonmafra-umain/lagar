package app.lagar.data

import app.lagar.domain.QueryTerm
import app.lagar.domain.shardKey
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** The fields a document matched in: [any] is the OR over the query terms, [all] the AND. */
data class FieldMatch(val any: Int, val all: Int)

/**
 * Client of the static search index. Reads the manifest once, then `docs.json` and only the shards the query
 * terms fall in. Everything is cached for the life of the process and keyed by the manifest's `built_at`, since
 * document numbers change between builds. Failures are not cached, except a missing index (HTTP 404), which is
 * remembered so the app falls back to the catalog without asking again.
 */
class FullTextIndex(private val source: SearchIndexSource) {
    private val lock = Mutex()
    private var manifest: SearchManifest? = null
    private var missing = false
    private var docs: List<ListingItem>? = null
    private val shards = mutableMapOf<String, SearchShard>()

    /** The manifest, or null when the API has no index or one of a version this app cannot read. */
    suspend fun manifest(): SearchManifest? = lock.withLock {
        if (missing) return@withLock null
        manifest?.let { return@withLock it }
        val loaded = try {
            source.searchManifest()
        } catch (e: ApiException) {
            if (e.notFound) {
                missing = true
                return@withLock null
            }
            throw e
        }
        if (loaded.searchVersion != SUPPORTED_VERSION) {
            missing = true
            return@withLock null
        }
        loaded.also { use(it) }
    }

    /** Whether the document table is already in memory, so a search needs at most a few small shards. */
    fun isWarm(): Boolean = docs != null

    /** Rows of `docs.json` as listing items; index = document number. */
    suspend fun docs(): List<ListingItem> {
        lock.withLock { docs }?.let { return it }
        val built = manifest() ?: error("no search index")
        val loaded = source.searchDocs().items()
        return lock.withLock {
            if (manifest?.builtAt == built.builtAt) docs = loaded
            loaded
        }
    }

    /**
     * Documents matching every term in a field of [mask], by document number. A prefix term matches every term
     * of its shard that starts with it. Returns an empty map as soon as one term has no match.
     */
    suspend fun match(terms: List<QueryTerm>, mask: Int): Map<Int, FieldMatch> {
        val built = manifest() ?: error("no search index")
        val keys = terms.map { shardKey(it.text) }
        if (keys.any { it !in built.shardKeys }) return emptyMap()
        val loaded = shards(keys.toSet(), built)
        return intersect(terms.map { termPostings(it, loaded.getValue(shardKey(it.text)), mask) })
    }

    private suspend fun shards(keys: Set<String>, built: SearchManifest): Map<String, SearchShard> {
        val cached = lock.withLock { keys.mapNotNull { k -> shards[k]?.let { k to it } }.toMap() }
        val fetched = coroutineScope {
            (keys - cached.keys).map { key -> async { key to source.searchShard(key) } }.awaitAll().toMap()
        }
        lock.withLock { if (manifest?.builtAt == built.builtAt) shards.putAll(fetched) }
        return cached + fetched
    }

    private fun use(loaded: SearchManifest) {
        if (manifest?.builtAt != loaded.builtAt) {
            docs = null
            shards.clear()
        }
        manifest = loaded
    }

    private companion object {
        const val SUPPORTED_VERSION = 1
    }
}

/** Decodes flat `[gap, bits, gap, bits, ...]` postings into (document number, field bits) pairs. */
internal fun decodePostings(flat: List<Int>): List<Pair<Int, Int>> {
    val out = ArrayList<Pair<Int, Int>>(flat.size / 2)
    var doc = 0
    for (i in 0 until flat.size - 1 step 2) {
        doc += flat[i]
        out += doc to flat[i + 1]
    }
    return out
}

/** Document -> field bits (within [mask], never 0) for one query term in its [shard]. */
internal fun termPostings(term: QueryTerm, shard: SearchShard, mask: Int): Map<Int, Int> {
    val out = HashMap<Int, Int>()
    val lists = if (term.prefix) {
        shard.terms.filterKeys { it.startsWith(term.text) }.values
    } else {
        listOfNotNull(shard.terms[term.text])
    }
    for (flat in lists) {
        for ((doc, bits) in decodePostings(flat)) {
            val masked = bits and mask
            if (masked != 0) out[doc] = (out[doc] ?: 0) or masked
        }
    }
    return out
}

/** Documents present for every term, with the OR and AND of their field bits. */
internal fun intersect(perTerm: List<Map<Int, Int>>): Map<Int, FieldMatch> {
    if (perTerm.isEmpty()) return emptyMap()
    val smallest = perTerm.minBy { it.size }
    val out = HashMap<Int, FieldMatch>()
    for (doc in smallest.keys) {
        var any = 0
        var all = -1
        var everywhere = true
        for (term in perTerm) {
            val bits = term[doc]
            if (bits == null) {
                everywhere = false
                break
            }
            any = any or bits
            all = all and bits
        }
        if (everywhere) out[doc] = FieldMatch(any, all)
    }
    return out
}
