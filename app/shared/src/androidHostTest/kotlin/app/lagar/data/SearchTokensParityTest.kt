package app.lagar.data

import app.lagar.domain.STOP_WORDS
import app.lagar.domain.Scope
import app.lagar.domain.SearchMode
import app.lagar.domain.SearchQuery
import app.lagar.domain.normalize
import app.lagar.domain.tokenize
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The app tokenises queries exactly like the API builds its index. Both sides are tested against the same
 * fixture (`api/tests/fixtures/search-tokens.json`, also read by `api/tests/test_search.py`), and the app's
 * fold table and stop words must equal the manifest's `normalization` block.
 */
class SearchTokensParityTest {
    // Host tests run from app/shared.
    private val repoRoot = File("../..")

    private fun json(path: String): JsonObject = Json.parseToJsonElement(File(repoRoot, path).readText()).jsonObject

    @Test
    fun tokensMatchTheSharedFixture() {
        val cases = json("api/tests/fixtures/search-tokens.json").getValue("cases").jsonArray
        assertTrue(cases.size > 5)
        for (case in cases) {
            val text = case.jsonObject.getValue("text").jsonPrimitive.content
            val expected = case.jsonObject.getValue("tokens").jsonArray.map { it.jsonPrimitive.content }
            assertEquals(expected, tokenize(text), "tokens of \"$text\"")
        }
    }

    @Test
    fun normalizationMatchesTheManifest() {
        val normalization = json("docs/api/examples/search/index.json").getValue("normalization").jsonObject
        val from = normalization.getValue("fold_from").jsonPrimitive.content
        val to = normalization.getValue("fold_to").jsonPrimitive.content
        assertEquals(to, normalize(from))
        val stopWords = normalization.getValue("stop_words").jsonArray.map { it.jsonPrimitive.content }.toSet()
        assertEquals(stopWords, STOP_WORDS)
    }

    @Test
    fun theBundledSampleHasAnIndexThatFullTextSearchUses() = runTest {
        val sample = SampleRepository { path -> File("src/commonMain/composeResources/$path").readBytes() }
        val index = FullTextIndex(sample)
        val service = SearchService(index, Catalog(sample))
        val manifest = index.manifest()
        assertEquals(2, manifest?.searchVersion)
        assertEquals(listOf("fundamental", "sfs", "region", "municipality"), manifest?.groups?.map { it.id })
        assertTrue(manifest!!.groups.all { it.fields.last() == "body" })
        val hits = service.search(SearchQuery("regeringsformen", mode = SearchMode.FullText), Scope.Nationell)
        assertTrue(hits.any { it.item.id == "sfs-1974-152" })
        assertEquals("sfs-1974-152", hits.first().item.id)
    }
}
