package app.lagar.data

import app.lagar.domain.QueryTerm
import app.lagar.domain.SearchField
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** A search index served from memory, built like docs/api/examples/search; counts what it serves. */
internal class FakeSearchSource(
    var builtAt: String = "2026-10-27T10:30:00Z",
    var missing: Boolean = false,
    var version: Int = 1,
) : SearchIndexSource {
    val shardRequests = mutableListOf<String>()
    var docsRequests = 0
    var manifestRequests = 0

    val shardData = mapOf(
        "19" to mapOf("1974:152" to listOf(0, 2), "1999:100" to listOf(1, 7)),
        "20" to mapOf("2010:800" to listOf(2, 3)),
        "ex" to mapOf("exempelforordning" to listOf(1, 1)),
        "fo" to mapOf("forordning" to listOf(1, 4, 1, 4), "foreskrift" to listOf(0, 4)),
        "re" to mapOf("regeringsformen" to listOf(0, 1)),
        "sk" to mapOf("skollag" to listOf(2, 1), "skola" to listOf(1, 4)),
        "ut" to mapOf("utbildning" to listOf(2, 4), "utgar" to listOf(0, 4)),
    )

    override suspend fun searchManifest(): SearchManifest {
        manifestRequests++
        if (missing) throw ApiException("missing", 404)
        return SearchManifest(
            searchVersion = version,
            builtAt = builtAt,
            docCount = 3,
            fields = listOf("title", "number", "body"),
            fieldBits = mapOf("title" to 1, "number" to 2, "body" to 4),
            shardKeyLength = 2,
            shards = shardData.map { (k, v) -> SearchShardInfo(k, v.size, 0) },
        )
    }

    override suspend fun searchDocs(): SearchDocsTable {
        docsRequests++
        return Json.decodeFromString(
            """
            {"fields": ["id", "title", "number", "type", "issued", "repealed"],
             "docs": [
               ["sfs-1974-152", "Regeringsformen", "1974:152", "fundamental_law", "1974-02-28", null],
               ["sfs-1999-100", "Exempelförordning (1999:100)", "1999:100", "ordinance", "1999-03-25", "2005-01-01"],
               ["sfs-2010-800", "Skollag (2010:800)", "2010:800", "act", "2010-06-23", null]
             ]}
            """,
        )
    }

    override suspend fun searchShard(key: String): SearchShard {
        shardRequests += key
        return SearchShard(key, shardData.getValue(key))
    }
}

class FullTextIndexTest {
    private val all = SearchField.TITLE or SearchField.NUMBER or SearchField.BODY

    @Test
    fun fetchesOnlyTheShardsOfTheQueryTerms() = runTest {
        val source = FakeSearchSource()
        val index = FullTextIndex(source)
        val hits = index.match(listOf(QueryTerm("skollag"), QueryTerm("utbildning")), all)
        assertEquals(setOf(2), hits.keys)
        assertEquals(setOf("sk", "ut"), source.shardRequests.toSet())
    }

    @Test
    fun shardsAreCachedAcrossQueries() = runTest {
        val source = FakeSearchSource()
        val index = FullTextIndex(source)
        index.match(listOf(QueryTerm("skollag")), all)
        index.match(listOf(QueryTerm("skola")), all)
        assertEquals(listOf("sk"), source.shardRequests)
        assertEquals(1, source.manifestRequests)
    }

    @Test
    fun aTermWithoutAShardMatchesNothingWithoutFetching() = runTest {
        val source = FakeSearchSource()
        val hits = FullTextIndex(source).match(listOf(QueryTerm("skollag"), QueryTerm("zzz")), all)
        assertTrue(hits.isEmpty())
        assertEquals(emptyList(), source.shardRequests)
    }

    @Test
    fun aPrefixMatchesEveryTermStartingWithIt() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        assertEquals(setOf(1, 2), index.match(listOf(QueryTerm("sko", prefix = true)), all).keys)
        assertEquals(emptySet(), index.match(listOf(QueryTerm("sko")), all).keys)
    }

    @Test
    fun theFieldMaskLimitsWhereATermMayMatch() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        val titleOnly = index.match(listOf(QueryTerm("forordning")), SearchField.TITLE)
        assertTrue(titleOnly.isEmpty())
        val body = index.match(listOf(QueryTerm("forordning")), all)
        assertEquals(setOf(1, 2), body.keys)
    }

    @Test
    fun intersectionKeepsTheFieldsOfEveryTerm() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        val hits = index.match(listOf(QueryTerm("1999:100"), QueryTerm("exempelforordning")), all)
        assertEquals(FieldMatch(any = 7, all = 1), hits.getValue(1))
    }

    @Test
    fun postingsAreGapEncoded() {
        assertEquals(listOf(1 to 4, 2 to 4, 7 to 1), decodePostings(listOf(1, 4, 1, 4, 5, 1)))
    }

    @Test
    fun aMissingIndexIsRememberedAsAbsent() = runTest {
        val source = FakeSearchSource(missing = true)
        val index = FullTextIndex(source)
        assertNull(index.manifest())
        assertNull(index.manifest())
        assertEquals(1, source.manifestRequests)
    }

    @Test
    fun anUnknownIndexVersionIsIgnored() = runTest {
        assertNull(FullTextIndex(FakeSearchSource(version = 2)).manifest())
    }

    @Test
    fun docsAreReadOnceAsListingItems() = runTest {
        val source = FakeSearchSource()
        val index = FullTextIndex(source)
        val docs = index.docs()
        index.docs()
        assertEquals(1, source.docsRequests)
        assertEquals("Exempelförordning (1999:100)", docs[1].title)
        assertEquals("2005-01-01", docs[1].repealed)
        assertNull(docs[1].inForce)
        assertTrue(index.isWarm())
    }

    @Test
    fun docsReadOptionalColumnsByName() {
        val table = Json.decodeFromString<SearchDocsTable>(
            """{"fields": ["title", "id", "in_force"], "docs": [["T", "x", "2027-01-01"]]}""",
        )
        val item = table.items().single()
        assertEquals("x", item.id)
        assertEquals("2027-01-01", item.inForce)
        assertNull(item.issued)
    }
}
