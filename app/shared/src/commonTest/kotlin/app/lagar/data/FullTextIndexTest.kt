package app.lagar.data

import app.lagar.domain.QueryTerm
import app.lagar.domain.SearchField
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * A search index served from memory, built like docs/api/examples/search; counts what it serves. [version] 2 (the
 * current API) splits the three documents into the groups `fundamental` (document 0) and `sfs` (documents 1 and 2,
 * numbered 0 and 1 within the group) with packed postings; version 1 is one index with `[gap, bits]` postings.
 */
internal class FakeSearchSource(
    var builtAt: String = "2026-10-27T10:30:00Z",
    var missing: Boolean = false,
    var version: Int = 2,
) : SearchIndexSource {
    val shardRequests = mutableListOf<String>()
    val groupManifestRequests = mutableListOf<String>()
    val docsRequests = mutableListOf<String?>()
    var manifestRequests = 0

    /** Version 1 shards: global document numbers, `[gap, bits, ...]`. */
    val shardData = mapOf(
        "19" to mapOf("1974:152" to listOf(0, 2), "1999:100" to listOf(1, 7)),
        "20" to mapOf("2010:800" to listOf(2, 3)),
        "ex" to mapOf("exempelforordning" to listOf(1, 1)),
        "fo" to mapOf("forordning" to listOf(1, 4, 1, 4), "foreskrift" to listOf(0, 4)),
        "re" to mapOf("regeringsformen" to listOf(0, 1)),
        "sk" to mapOf("skollag" to listOf(2, 1), "skola" to listOf(1, 4)),
        "ut" to mapOf("utbildning" to listOf(2, 4), "utgar" to listOf(0, 4)),
    )

    private val rows = listOf(
        """["sfs-1974-152", "Regeringsformen", "1974:152", "fundamental_law", "1974-02-28", null]""",
        """["sfs-1999-100", "Exempelförordning (1999:100)", "1999:100", "ordinance", "1999-03-25", "2005-01-01"]""",
        """["sfs-2010-800", "Skollag (2010:800)", "2010:800", "act", "2010-06-23", null]""",
    )

    /** Group id -> its global document numbers, in group order. */
    private val groupDocs = linkedMapOf("fundamental" to listOf(0), "sfs" to listOf(1, 2))

    /** Version 2 shards of [group]: postings re-numbered within the group and packed as `gap * 8 + bits`. */
    private fun groupShards(group: String): Map<String, Map<String, List<Int>>> {
        val members = groupDocs.getValue(group)
        return shardData.mapValues { (_, terms) ->
            terms.mapValues { (_, flat) ->
                var prev = 0
                decodePostings(flat).filter { it.first in members }.map { (doc, bits) ->
                    val local = members.indexOf(doc)
                    ((local - prev) * 8 + bits).also { prev = local }
                }
            }.filterValues { it.isNotEmpty() }
        }.filterValues { it.isNotEmpty() }
    }

    override suspend fun searchManifest(): SearchManifest {
        manifestRequests++
        if (missing) throw ApiException("missing", 404)
        val fields = listOf("title", "number", "body")
        val bits = mapOf("title" to 1, "number" to 2, "body" to 4)
        return if (version == 1) {
            SearchManifest(
                searchVersion = 1,
                builtAt = builtAt,
                docCount = 3,
                fields = fields,
                fieldBits = bits,
                shards = shardData.map { (k, v) -> SearchShardInfo(k, v.size, 0) },
            )
        } else {
            SearchManifest(
                searchVersion = version,
                builtAt = builtAt,
                docCount = 3,
                fieldBits = bits,
                groups = groupDocs.map { (id, docs) -> SearchGroupInfo(id, listOf(id), docs.size, fields) },
                postingBitsBase = 8,
            )
        }
    }

    override suspend fun searchGroupManifest(group: String): SearchGroupManifest {
        groupManifestRequests += group
        val shards = groupShards(group)
        return SearchGroupManifest(group, listOf(group), groupDocs.getValue(group).size, listOf("title", "number", "body"), shards.map { (k, v) -> SearchShardInfo(k, v.size, 0) })
    }

    override suspend fun searchDocs(group: String?): SearchDocsTable {
        docsRequests += group
        val members = if (group == null) rows.indices.toList() else groupDocs.getValue(group)
        return Json.decodeFromString(
            """{"fields": ["id", "title", "number", "type", "issued", "repealed"], "docs": [${members.joinToString { rows[it] }}]}""",
        )
    }

    override suspend fun searchShard(group: String?, key: String): SearchShard {
        shardRequests += if (group == null) key else "$group/$key"
        return SearchShard(key, if (group == null) shardData.getValue(key) else groupShards(group).getValue(key))
    }
}

class FullTextIndexTest {
    private val all = SearchField.TITLE or SearchField.NUMBER or SearchField.BODY

    private suspend fun FullTextIndex.group(id: String) = groups().single { it.id == id }

    @Test
    fun fetchesOnlyTheShardsOfTheQueryTerms() = runTest {
        val source = FakeSearchSource()
        val index = FullTextIndex(source)
        val hits = index.match(index.group("sfs"), listOf(QueryTerm("skollag"), QueryTerm("utbildning")), all)
        assertEquals(setOf(1), hits.keys)
        assertEquals(setOf("sfs/sk", "sfs/ut"), source.shardRequests.toSet())
        assertEquals(listOf("sfs"), source.groupManifestRequests)
    }

    @Test
    fun shardsAndGroupManifestsAreCachedAcrossQueries() = runTest {
        val source = FakeSearchSource()
        val index = FullTextIndex(source)
        val sfs = index.group("sfs")
        index.match(sfs, listOf(QueryTerm("skollag")), all)
        index.match(sfs, listOf(QueryTerm("skola")), all)
        assertEquals(listOf("sfs/sk"), source.shardRequests)
        assertEquals(listOf("sfs"), source.groupManifestRequests)
        assertEquals(1, source.manifestRequests)
    }

    @Test
    fun aTermWithoutAShardMatchesNothingWithoutFetching() = runTest {
        val source = FakeSearchSource()
        val index = FullTextIndex(source)
        val hits = index.match(index.group("sfs"), listOf(QueryTerm("skollag"), QueryTerm("zzz")), all)
        assertTrue(hits.isEmpty())
        assertEquals(emptyList(), source.shardRequests)
        // `regeringsformen` is only in the fundamental group, so the sfs group has no `re` shard.
        assertTrue(index.match(index.group("sfs"), listOf(QueryTerm("regeringsformen")), all).isEmpty())
        assertEquals(emptyList(), source.shardRequests)
    }

    @Test
    fun aPrefixMatchesEveryTermStartingWithIt() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        assertEquals(setOf(0, 1), index.match(index.group("sfs"), listOf(QueryTerm("sko", prefix = true)), all).keys)
        assertEquals(emptySet(), index.match(index.group("sfs"), listOf(QueryTerm("sko")), all).keys)
    }

    @Test
    fun aTermsBaseIsMatchedExactly() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        val sfs = index.group("sfs")
        assertEquals(setOf(1), index.match(sfs, listOf(QueryTerm("skollagen", base = "skollag")), all).keys)
        assertTrue(index.match(sfs, listOf(QueryTerm("skollagen")), all).isEmpty())
    }

    @Test
    fun theFieldMaskLimitsWhereATermMayMatch() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        val sfs = index.group("sfs")
        assertTrue(index.match(sfs, listOf(QueryTerm("forordning")), SearchField.TITLE).isEmpty())
        assertEquals(setOf(0, 1), index.match(sfs, listOf(QueryTerm("forordning")), all).keys)
    }

    @Test
    fun intersectionKeepsTheFieldsOfEveryTerm() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        val hits = index.match(index.group("sfs"), listOf(QueryTerm("1999:100"), QueryTerm("exempelforordning")), all)
        assertEquals(FieldMatch(any = 7, all = 1), hits.getValue(0))
    }

    @Test
    fun postingsDecodeInBothVersions() {
        assertEquals(listOf(1 to 4, 2 to 4, 7 to 1), decodePostings(listOf(1, 4, 1, 4, 5, 1)))
        assertEquals(listOf(1 to 4, 2 to 4, 7 to 1), decodePostings(listOf(12, 12, 41), base = 8))
    }

    @Test
    fun groupsAreChosenByLayer() = runTest {
        val index = FullTextIndex(FakeSearchSource())
        assertEquals(listOf("fundamental", "sfs"), index.groups().map { it.id })
        assertEquals(listOf("sfs"), index.groups(setOf("sfs", "case_law")).map { it.id })
        assertEquals(emptyList(), index.groups(setOf("municipality")))
    }

    @Test
    fun docsAreReadOncePerGroupAndOnlyForTheRequestedLayers() = runTest {
        val source = FakeSearchSource()
        val index = FullTextIndex(source)
        val sfs = index.docs(setOf("sfs"))
        index.docs(setOf("sfs"))
        assertEquals(listOf<String?>("sfs"), source.docsRequests)
        assertEquals(listOf("sfs-1999-100", "sfs-2010-800"), sfs.map { it.id })
        assertEquals("2005-01-01", sfs[0].repealed)
        assertNull(sfs[0].inForce)
        assertTrue(index.isWarm(setOf("sfs")))
        assertFalse(index.isWarm(setOf("fundamental", "sfs")))
        assertEquals(listOf("sfs-1974-152", "sfs-1999-100", "sfs-2010-800"), index.docs().map { it.id })
        assertEquals(listOf<String?>("sfs", "fundamental"), source.docsRequests)
        assertTrue(index.isWarm())
    }

    @Test
    fun aVersionOneIndexIsOneGroupOverEveryLayer() = runTest {
        val source = FakeSearchSource(version = 1)
        val index = FullTextIndex(source)
        val groups = index.groups(setOf("sfs"))
        assertEquals(listOf(IndexGroup(null, null, listOf("title", "number", "body"))), groups)
        assertEquals(groups, index.groups(setOf("municipality")))
        val hits = index.match(groups.single(), listOf(QueryTerm("skollag"), QueryTerm("utbildning")), all)
        assertEquals(setOf(2), hits.keys)
        assertEquals(FieldMatch(7, 1), index.match(groups.single(), listOf(QueryTerm("1999:100"), QueryTerm("exempelforordning")), all).getValue(1))
        assertEquals(listOf("sk", "ut", "19", "ex"), source.shardRequests)
        assertEquals(emptyList(), source.groupManifestRequests)
        assertEquals(3, index.docs(setOf("sfs")).size)
        assertEquals(listOf<String?>(null), source.docsRequests)
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
        assertNull(FullTextIndex(FakeSearchSource(version = 3)).manifest())
        assertEquals(1, FullTextIndex(FakeSearchSource(version = 1)).manifest()?.searchVersion)
        assertEquals(2, FullTextIndex(FakeSearchSource(version = 2)).manifest()?.searchVersion)
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

    @Test
    fun manifestsOfBothVersionsDecode() {
        val json = Json { ignoreUnknownKeys = true }
        val v1 = json.decodeFromString<SearchManifest>(
            """{"search_version": 1, "built_at": "t", "doc_count": 3, "term_count": 9, "fields": ["title", "number"],
               "field_bits": {"title": 1, "number": 2}, "shard_key_length": 2, "shards": [{"key": "sk", "terms": 1, "bytes": 9}]}""",
        )
        assertEquals(listOf(IndexGroup(null, null, listOf("title", "number"))), v1.indexGroups())
        assertNull(v1.postingBase)
        val v2 = json.decodeFromString<SearchManifest>(
            """{"search_version": 2, "built_at": "t", "doc_count": 3, "term_count": 9, "field_bits": {"title": 1},
               "posting_bits_base": 8, "shard_key_length": 2,
               "groups": [{"id": "case_law", "layers": ["case_law"], "doc_count": 3, "fields": ["title", "number"], "bytes": 9, "budget": 9}]}""",
        )
        assertEquals(listOf(IndexGroup("case_law", setOf("case_law"), listOf("title", "number"))), v2.indexGroups())
        assertEquals(8, v2.postingBase)
    }
}
