package app.lagar.data

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class GzipTest {
    // Python: gzip.compress(DOCUMENT.encode(), compresslevel=9, mtime=0), as api/build.py writes documents.
    private val document = """{"meta":{"id":"sfs-2010-800"},"body":"# Skollag\n\nÅre åäö "}"""
    private val documentGzip = bytes(
        31, -117, 8, 0, 0, 0, 0, 0, 2, -1, -85, 86, -54, 77, 45, 73, 84, -78, -86, 86, -54, 76, 81, -78, 82, 42, 78,
        43, -42, 53, 50, 48, 52, -48, -75, 48, 48, 80, -86, -43, 81, 74, -54, 79, -87, 4, 10, 43, 43, 4, 103, -25, -25,
        -28, 36, -90, -57, -28, -59, -28, 29, 110, 45, 74, 85, 56, -68, -12, -16, -110, -61, -37, 20, -108, 106, 1, 53,
        61, -118, -34, 65, 0, 0, 0,
    )

    // A stored (level 0) block, with a file name in the header.
    private val storedWithName = bytes(
        31, -117, 8, 8, 0, 0, 0, 0, 0, -1, 120, 46, 116, 120, 116, 0, 1, 24, 0, -25, -1, 104, 101, 108, 108, 111, 32,
        104, 101, 108, 108, 111, 32, 104, 101, 108, 108, 111, 32, 104, 101, 108, 108, 111, 10, 0, -120, 89, 11, 24, 0,
        0, 0,
    )

    @Test
    fun decompressesADocument() {
        assertEquals(document, Gzip.decompress(documentGzip).decodeToString())
    }

    @Test
    fun readsStoredBlocksAndSkipsTheFileName() {
        assertEquals("hello hello hello hello\n", Gzip.decompress(storedWithName).decodeToString())
    }

    @Test
    fun rejectsCorruptData() {
        assertFailsWith<IllegalArgumentException> { Gzip.decompress(document.encodeToByteArray()) }
        assertFailsWith<IllegalArgumentException> { Gzip.decompress(documentGzip.copyOf(40)) }
        val badChecksum = documentGzip.copyOf().also { it[it.size - 8] = (it[it.size - 8] + 1).toByte() }
        assertFailsWith<IllegalArgumentException> { Gzip.decompress(badChecksum) }
    }

    @Test
    fun crc32MatchesTheStandardCheckValue() {
        assertEquals(0xCBF43926L, Gzip.crc32("123456789".encodeToByteArray()))
    }

    private fun bytes(vararg values: Int) = ByteArray(values.size) { values[it].toByte() }
}
