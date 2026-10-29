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
 * One part of the index, searched on its own with its own document numbers: a version 2 group (one layer), or the
 * whole version 1 index ([id] null, [layers] null for every layer).
 */
data class IndexGroup(val id: String?, val layers: Set<String>?, val fields: List<String>) {
    /** Whether this group holds documents of any of [apiLayers]; null means every layer. */
    fun covers(apiLayers: Set<String>?): Boolean = layers == null || apiLayers == null || layers.any { it in apiLayers }
}

/**
 * Client of the static search index, versions 1 and 2 (docs/api.md, "Full-text search"). Reads the top-level
 * manifest once; for each group a search needs, it reads the group's manifest (version 2), `docs.json` and only
 * the shards the query terms fall in. Everything is cached for the life of the process and keyed by the manifest's
 * `built_at`, since document numbers change between builds. Failures are not cached, except a missing index
 * (HTTP 404) or one of a version this app cannot read, which is remembered so the app falls back to the catalog
 * without asking again.
 */
class FullTextIndex(private val source: SearchIndexSource) {
    private val lock = Mutex()
    private var manifest: SearchManifest? = null
    private var missing = false
    private val groupManifests = mutableMapOf<String, SearchGroupManifest>()
    private val docs = mutableMapOf<String?, List<ListingItem>>()
    private val shards = mutableMapOf<Pair<String?, String>, SearchShard>()

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
        if (loaded.searchVersion !in SUPPORTED_VERSIONS) {
            missing = true
            return@withLock null
        }
        loaded.also { use(it) }
    }

    /** The groups holding documents of [apiLayers] (API layer ids; null for every layer), in manifest order. */
    suspend fun groups(apiLayers: Set<String>? = null): List<IndexGroup> {
        val built = manifest() ?: error("no search index")
        return built.indexGroups().filter { it.covers(apiLayers) }
    }

    /** Whether the document tables of [apiLayers] are in memory, so a search needs at most a few small shards. */
    fun isWarm(apiLayers: Set<String>? = null): Boolean {
        val built = manifest ?: return false
        return built.indexGroups().filter { it.covers(apiLayers) }.all { it.id in docs }
    }

    /** Rows of the `docs.json` of the groups holding [apiLayers] (null for every layer), group after group. */
    suspend fun docs(apiLayers: Set<String>? = null): List<ListingItem> = groups(apiLayers).flatMap { docs(it) }

    /** Rows of [group]'s `docs.json` as listing items; index = document number within the group. */
    suspend fun docs(group: IndexGroup): List<ListingItem> {
        lock.withLock { docs[group.id] }?.let { return it }
        val built = manifest() ?: error("no search index")
        val loaded = source.searchDocs(group.id).items()
        return lock.withLock {
            if (manifest?.builtAt == built.builtAt) docs[group.id] = loaded
            loaded
        }
    }

    /**
     * Documents of [group] matching every term in a field of [mask], by document number within the group. A prefix
     * term matches every term of its shard that starts with it. Returns an empty map as soon as one term has no
     * match.
     */
    suspend fun match(group: IndexGroup, terms: List<QueryTerm>, mask: Int): Map<Int, FieldMatch> {
        val built = manifest() ?: error("no search index")
        val keys = terms.map { shardKey(it.text) }
        if (keys.any { it !in shardKeys(group, built) }) return emptyMap()
        val loaded = shards(group, keys.toSet(), built)
        val base = built.postingBase
        return intersect(terms.map { termPostings(it, loaded.getValue(shardKey(it.text)), mask, base) })
    }

    private suspend fun shardKeys(group: IndexGroup, built: SearchManifest): Set<String> {
        val id = group.id ?: return built.shards.mapTo(HashSet()) { it.key }
        lock.withLock { groupManifests[id] }?.let { return it.shardKeys() }
        val loaded = source.searchGroupManifest(id)
        lock.withLock { if (manifest?.builtAt == built.builtAt) groupManifests[id] = loaded }
        return loaded.shardKeys()
    }

    private suspend fun shards(group: IndexGroup, keys: Set<String>, built: SearchManifest): Map<String, SearchShard> {
        val cached = lock.withLock { keys.mapNotNull { k -> shards[group.id to k]?.let { k to it } }.toMap() }
        val fetched = coroutineScope {
            (keys - cached.keys).map { key -> async { key to source.searchShard(group.id, key) } }.awaitAll().toMap()
        }
        lock.withLock {
            if (manifest?.builtAt == built.builtAt) fetched.forEach { (k, v) -> shards[group.id to k] = v }
        }
        return cached + fetched
    }

    private fun use(loaded: SearchManifest) {
        if (manifest?.builtAt != loaded.builtAt) {
            groupManifests.clear()
            docs.clear()
            shards.clear()
        }
        manifest = loaded
    }

    private companion object {
        val SUPPORTED_VERSIONS = setOf(1, 2)
    }
}

/** The searchable parts of this index: one per version 2 group, or the whole version 1 index. */
internal fun SearchManifest.indexGroups(): List<IndexGroup> = if (searchVersion == 1) {
    listOf(IndexGroup(null, null, fields))
} else {
    groups.map { IndexGroup(it.id, it.layers.toSet(), it.fields) }
}

/** The `posting_bits_base` of a version 2 index (8 when the manifest leaves it out); null for version 1 pairs. */
internal val SearchManifest.postingBase: Int?
    get() = if (searchVersion == 1) null else postingBitsBase ?: DEFAULT_POSTING_BASE

private const val DEFAULT_POSTING_BASE = 8

private fun SearchGroupManifest.shardKeys(): Set<String> = shards.mapTo(HashSet()) { it.key }

/**
 * Decodes postings into (document number, field bits) pairs. Version 1 ([base] null) is flat `[gap, bits, ...]`;
 * version 2 packs each posting as `gap * base + bits`. The first gap is the document number itself.
 */
internal fun decodePostings(flat: List<Int>, base: Int? = null): List<Pair<Int, Int>> {
    if (base != null) {
        var doc = 0
        return flat.map { value ->
            doc += value / base
            doc to value % base
        }
    }
    val out = ArrayList<Pair<Int, Int>>(flat.size / 2)
    var doc = 0
    for (i in 0 until flat.size - 1 step 2) {
        doc += flat[i]
        out += doc to flat[i + 1]
    }
    return out
}

/** Document -> field bits (within [mask], never 0) for one query term in its [shard]; [base] as in [decodePostings]. */
internal fun termPostings(term: QueryTerm, shard: SearchShard, mask: Int, base: Int? = null): Map<Int, Int> {
    val out = HashMap<Int, Int>()
    val lists = if (term.prefix) {
        shard.terms.filterKeys { it.startsWith(term.text) }.values
    } else {
        listOfNotNull(shard.terms[term.text])
    }
    for (flat in lists) {
        for ((doc, bits) in decodePostings(flat, base)) {
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
