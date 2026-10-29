package app.lagar.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive

/**
 * `search/index.json`: the manifest of the static full-text index (docs/api.md, "Full-text search"). Version 1 is
 * one index over every layer, with its [shards] listed here; version 2 lists one [groups] entry per layer, each with
 * its own manifest, document table and shards under `search/<group>/`.
 */
@Serializable
data class SearchManifest(
    @SerialName("search_version") val searchVersion: Int,
    @SerialName("built_at") val builtAt: String,
    @SerialName("doc_count") val docCount: Int = 0,
    val fields: List<String> = emptyList(),
    @SerialName("field_bits") val fieldBits: Map<String, Int> = emptyMap(),
    @SerialName("shard_key_length") val shardKeyLength: Int = 2,
    val shards: List<SearchShardInfo> = emptyList(),
    val groups: List<SearchGroupInfo> = emptyList(),
    @SerialName("posting_bits_base") val postingBitsBase: Int? = null,
)

/** A version 2 group as the top-level manifest lists it: the layers it covers and whether bodies are indexed. */
@Serializable
data class SearchGroupInfo(
    val id: String,
    val layers: List<String>,
    @SerialName("doc_count") val docCount: Int,
    val fields: List<String>,
)

/** `search/<group>/index.json`: the shards of one version 2 group. */
@Serializable
data class SearchGroupManifest(
    val group: String,
    val layers: List<String>,
    @SerialName("doc_count") val docCount: Int,
    val fields: List<String>,
    val shards: List<SearchShardInfo>,
)

@Serializable
data class SearchShardInfo(val key: String, val terms: Int, val bytes: Int)

/** `search/docs.json`: one row per document, columns named by [fields]; a row's index is its document number. */
@Serializable
data class SearchDocsTable(val fields: List<String>, val docs: List<List<JsonElement>>) {
    /**
     * Rows as listing items. Columns are read by name, so a column the API adds later (such as `in_force`) is
     * picked up and a missing optional one is null.
     */
    fun items(): List<ListingItem> {
        val col = fields.withIndex().associate { (i, name) -> name to i }

        fun List<JsonElement>.text(name: String): String? {
            val element = col[name]?.let { getOrNull(it) } ?: return null
            return if (element is JsonPrimitive && element !is JsonNull) element.content else null
        }
        return docs.map { row ->
            ListingItem(
                id = row.text("id").orEmpty(),
                title = row.text("title").orEmpty(),
                number = row.text("number").orEmpty(),
                type = row.text("type").orEmpty(),
                issued = row.text("issued"),
                repealed = row.text("repealed"),
                inForce = row.text("in_force"),
                amendedThrough = row.text("amended_through"),
                ministry = row.text("ministry"),
                regionCode = row.text("region_code"),
                municipalityCode = row.text("municipality_code"),
            )
        }
    }
}

/** `search/shards/<key>.json`: term -> flat `[gap, bits, gap, bits, ...]` postings. */
@Serializable
data class SearchShard(val key: String, val terms: Map<String, List<Int>>)

/**
 * Read access to the static search index. [group] is a version 2 group id, or null for the single version 1 index.
 * A missing index surfaces as [ApiException] with [ApiException.notFound].
 */
interface SearchIndexSource {
    suspend fun searchManifest(): SearchManifest

    suspend fun searchGroupManifest(group: String): SearchGroupManifest

    suspend fun searchDocs(group: String?): SearchDocsTable

    suspend fun searchShard(group: String?, key: String): SearchShard
}

internal fun searchManifestPath() = "search/index.json"

private fun searchDir(group: String?) = if (group == null) "search/" else "search/$group/"

internal fun searchGroupManifestPath(group: String) = "${searchDir(group)}index.json"

internal fun searchDocsPath(group: String?) = "${searchDir(group)}docs.json"

internal fun searchShardPath(group: String?, key: String) = "${searchDir(group)}shards/$key.json"
