package app.lagar.tokens

import java.io.File
import kotlin.test.Test
import kotlin.test.assertTrue

class TokenGeneratorTest {
    private val source: String by lazy {
        val designMd = generateSequence(File("").absoluteFile) { it.parentFile }
            .map { File(it, "DESIGN.md") }
            .first { it.isFile }
        TokenGenerator.generate(designMd.readText())
    }

    private fun block(name: String): String {
        val start = source.indexOf("object $name")
        assertTrue(start >= 0, "missing object $name")
        return source.substring(start)
    }

    @Test
    fun lightPrimaryColor() {
        assertTrue("val primary = Color(0xFF004373)" in block("LightTokens").substringBefore("object DarkTokens"))
    }

    @Test
    fun darkPrimaryColor() {
        assertTrue("val primary = Color(0xFF9ECAFF)" in block("DarkTokens").substringBefore("enum class LayerKey"))
    }

    @Test
    fun serviceLayerText() {
        assertTrue("LayerKey.Service -> Color(0xFF8C6300)" in block("LayerTokens").substringBefore("fun dark"))
    }
}
