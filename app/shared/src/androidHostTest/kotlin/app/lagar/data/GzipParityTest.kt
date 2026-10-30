package app.lagar.data

import java.io.ByteArrayOutputStream
import java.util.zip.Deflater
import java.util.zip.GZIPOutputStream
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals

/** The common inflate decodes what the JVM's zlib writes, at every level, for random and repetitive data. */
class GzipParityTest {
    private fun gzip(data: ByteArray, level: Int): ByteArray {
        val buffer = ByteArrayOutputStream()
        object : GZIPOutputStream(buffer) {
            init {
                def.setLevel(level)
            }
        }.use { it.write(data) }
        return buffer.toByteArray()
    }

    @Test
    fun matchesZlibAtEveryLevel() {
        val random = Random(594)
        val words = listOf("lag ", "förordning ", "§ ", "1 kap. ", "Åre ", "\n\n", "**2 §** ")
        val inputs = listOf(
            ByteArray(0),
            byteArrayOf(42),
            random.nextBytes(70_000),
            buildString { repeat(40_000) { append(words[random.nextInt(words.size)]) } }.encodeToByteArray(),
            ByteArray(300_000) { (it % 251).toByte() },
        )
        for (data in inputs) {
            for (level in listOf(Deflater.NO_COMPRESSION, Deflater.BEST_SPEED, 6, Deflater.BEST_COMPRESSION)) {
                assertContentEquals(data, Gzip.decompress(gzip(data, level)), "size ${data.size}, level $level")
            }
        }
    }
}
