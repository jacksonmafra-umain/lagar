package app.lagar.tokens

import org.yaml.snakeyaml.Yaml

/** Turns the YAML frontmatter of DESIGN.md into the Kotlin source of the generated design tokens. */
object TokenGenerator {
    private const val PACKAGE = "app.lagar.designsystem.generated"

    fun generate(designMd: String): String {
        val front = frontmatter(designMd)
        @Suppress("UNCHECKED_CAST")
        val root = Yaml().load<Map<String, Any?>>(front)

        val out = StringBuilder()
        out.appendLine("// Generated from DESIGN.md by the design-tokens build plugin. Do not edit.")
        out.appendLine("package $PACKAGE")
        out.appendLine()
        out.appendLine("import androidx.compose.ui.graphics.Color")
        out.appendLine("import androidx.compose.ui.unit.Dp")
        out.appendLine("import androidx.compose.ui.unit.dp")
        out.appendLine()
        colorObject(out, "LightTokens", map(root, "colors"))
        colorObject(out, "DarkTokens", map(root, "colors-dark"))
        layers(out, map(root, "layers"))
        typography(out, map(root, "typography"))
        dimensions(out, "SpacingTokens", map(root, "spacing"))
        dimensions(out, "RadiusTokens", map(root, "rounded"))
        return out.toString()
    }

    private fun frontmatter(text: String): String {
        val lines = text.lines()
        val start = lines.indexOfFirst { it.trim() == "---" }
        require(start >= 0) { "DESIGN.md has no frontmatter" }
        val end = (start + 1 until lines.size).firstOrNull { lines[it].trim() == "---" }
        require(end != null) { "DESIGN.md frontmatter is not closed" }
        return lines.subList(start + 1, end).joinToString("\n")
    }

    @Suppress("UNCHECKED_CAST")
    private fun map(root: Map<String, Any?>, key: String): Map<String, Any?> =
        requireNotNull(root[key] as? Map<String, Any?>) { "DESIGN.md frontmatter is missing '$key'" }

    fun camel(key: String): String =
        key.split('-').mapIndexed { i, part ->
            val lower = if (part.all { it.isUpperCase() }) part.lowercase() else part
            if (i == 0) lower else lower.replaceFirstChar { it.uppercase() }
        }.joinToString("")

    fun pascal(key: String): String = camel(key).replaceFirstChar { it.uppercase() }

    private fun color(hex: Any?): String {
        val value = hex.toString().removePrefix("#").uppercase()
        require(value.length == 6) { "Unsupported color '$hex'" }
        return "Color(0xFF$value)"
    }

    private fun colorObject(out: StringBuilder, name: String, colors: Map<String, Any?>) {
        out.appendLine("object $name {")
        colors.forEach { (k, v) -> out.appendLine("    val ${camel(k)} = ${color(v)}") }
        out.appendLine("}")
        out.appendLine()
    }

    @Suppress("UNCHECKED_CAST")
    private fun layers(out: StringBuilder, layers: Map<String, Any?>) {
        out.appendLine("enum class LayerKey {")
        out.appendLine(layers.keys.joinToString(",\n") { "    ${pascal(it)}" })
        out.appendLine("}")
        out.appendLine()
        out.appendLine("object LayerTokens {")
        for (variant in listOf("base", "text", "dark")) {
            out.appendLine("    fun $variant(k: LayerKey): Color = when (k) {")
            layers.forEach { (k, v) ->
                out.appendLine("        LayerKey.${pascal(k)} -> ${color((v as Map<String, Any?>).getValue(variant))}")
            }
            out.appendLine("    }")
            if (variant != "dark") out.appendLine()
        }
        out.appendLine("}")
        out.appendLine()
    }

    private fun num(n: Number): String {
        val d = n.toDouble()
        return if (d == Math.rint(d)) "${d.toLong()}.0f" else "${"%.4f".format(java.util.Locale.ROOT, d).trimEnd('0')}f"
    }

    private fun rem(value: Any?): Double {
        val s = value.toString()
        return when {
            s.endsWith("rem") -> s.removeSuffix("rem").toDouble() * 16
            s.endsWith("px") -> s.removeSuffix("px").toDouble()
            else -> error("Unsupported length '$s'")
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun typography(out: StringBuilder, styles: Map<String, Any?>) {
        out.appendLine("enum class FontKey { Inter, SourceSerif4 }")
        out.appendLine()
        out.appendLine("data class TextStyleSpec(")
        out.appendLine("    val sizeSp: Float,")
        out.appendLine("    val lineHeightSp: Float,")
        out.appendLine("    val weight: Int,")
        out.appendLine("    val letterSpacingEm: Float,")
        out.appendLine("    val family: FontKey,")
        out.appendLine(")")
        out.appendLine()
        out.appendLine("object TypeTokens {")
        styles.forEach { (k, v) ->
            val s = v as Map<String, Any?>
            val family = when (val f = s.getValue("fontFamily").toString()) {
                "Inter" -> "Inter"
                "Source Serif 4" -> "SourceSerif4"
                else -> error("Unsupported font family '$f'")
            }
            val spacing = s.getValue("letterSpacing").toString().removeSuffix("em").toDouble()
            out.appendLine("    val ${camel(k)} = TextStyleSpec(")
            out.appendLine("        sizeSp = ${num(rem(s.getValue("fontSize")))},")
            out.appendLine("        lineHeightSp = ${num(rem(s.getValue("lineHeight")))},")
            out.appendLine("        weight = ${s.getValue("fontWeight").toString().toInt()},")
            out.appendLine("        letterSpacingEm = ${num(spacing)},")
            out.appendLine("        family = FontKey.$family,")
            out.appendLine("    )")
        }
        out.appendLine("}")
        out.appendLine()
    }

    private fun dimensions(out: StringBuilder, name: String, values: Map<String, Any?>) {
        out.appendLine("object $name {")
        values.forEach { (k, v) -> out.appendLine("    val ${camel(k)}: Dp = ${num(rem(v))}.dp") }
        out.appendLine("}")
        out.appendLine()
    }
}
