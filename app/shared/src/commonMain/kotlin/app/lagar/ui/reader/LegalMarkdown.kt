package app.lagar.ui.reader

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.withStyle
import app.lagar.designsystem.LagarTheme
import com.mikepenz.markdown.m3.Markdown
import com.mikepenz.markdown.m3.markdownColor
import com.mikepenz.markdown.m3.markdownTypography
import com.mikepenz.markdown.model.markdownAnnotator
import com.mikepenz.markdown.model.markdownPadding
import com.mikepenz.markdown.model.parseMarkdown
import org.intellij.markdown.MarkdownElementTypes

/** Longest line the reader allows, in characters; DESIGN.md asks for 60-75ch. */
private const val MAX_LINE_CHARS = 70

/** Average glyph width of the legal serif, as a fraction of the font size. */
private const val AVERAGE_CHAR_EM = 0.5f

/** Centers content and caps it at about [MAX_LINE_CHARS] characters of legal text; the cap scales with the font. */
@Composable
internal fun Modifier.readingColumn(): Modifier {
    val max = with(LocalDensity.current) { (LagarTheme.type.bodyLegalMd.fontSize * (MAX_LINE_CHARS * AVERAGE_CHAR_EM)).toDp() }
    return fillMaxWidth().widthIn(max = max)
}

/**
 * Renders one section of a legal text. Parsing is synchronous so a chapter has its final height on
 * its first frame (the library's string overload parses asynchronously and would make the list jump).
 * Paragraphs use `bodyLegalMd` (Source Serif 4); `**N §**` numbers switch to bold Inter (`statuteNum`)
 * through a custom annotator, since the stock strong span only changes the weight, not the family.
 */
@Composable
internal fun LegalMarkdown(content: String, modifier: Modifier = Modifier) {
    val type = LagarTheme.type
    val colors = LagarTheme.colors
    val state = remember(content) { parseMarkdown(content) }
    val annotator = remember(type) {
        markdownAnnotator { text, node ->
            if (node.type != MarkdownElementTypes.STRONG) return@markdownAnnotator false
            val inner = text.substring(node.startOffset, node.endOffset).removeSurrounding("**")
            if (!inner.endsWith("§")) return@markdownAnnotator false
            withStyle(type.statuteNum.toSpanStyle()) { append(inner) }
            true
        }
    }
    Markdown(
        state = state,
        colors = markdownColor(text = colors.onSurface),
        typography = markdownTypography(
            h1 = type.headlineMd,
            h2 = type.headlineSm,
            h3 = type.statuteNum,
            h4 = type.labelMd,
            h5 = type.labelMd,
            h6 = type.labelMd,
            text = type.bodyLegalMd,
            paragraph = type.bodyLegalMd,
            ordered = type.bodyLegalMd,
            bullet = type.bodyLegalMd,
            list = type.bodyLegalMd,
            quote = type.bodyLegalMd,
        ),
        padding = markdownPadding(block = LagarTheme.spacing.sm),
        annotator = annotator,
        modifier = modifier,
    )
}
