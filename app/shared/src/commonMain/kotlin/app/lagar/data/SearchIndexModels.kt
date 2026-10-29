package app.lagar.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive

/** `search/index.json`: the manifest of the static full-text index (docs/api.md, "Full-text search"). */
@Serializable
data class SearchManifest(
    @SerialName("search_version") val searchVersion: Int,
    @SerialName("built_at") val builtAt: String,
    @SerialName("doc_count") val docCount: Int,
    val fields: List<String>,
    @SerialName("field_bits") val fieldBits: Map<String, Int>,
    @SerialName("shard_key_length") val shardKeyLength: Int,
    val shards: List<SearchShardInfo>,
) {
    val shardKeys: Set<String> by lazy { shards.mapTo(HashSet()) { it.key } }
}

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

/** Read access to the static search index. A missing index surfaces as [ApiException] with [ApiException.notFound]. */
interface SearchIndexSource {
    suspend fun searchManifest(): SearchManifest

    suspend fun searchDocs(): SearchDocsTable

    suspend fun searchShard(key: String): SearchShard
}

internal fun searchManifestPath() = "search/index.json"

internal fun searchDocsPath() = "search/docs.json"

internal fun searchShardPath(key: String) = "search/shards/$key.json"
