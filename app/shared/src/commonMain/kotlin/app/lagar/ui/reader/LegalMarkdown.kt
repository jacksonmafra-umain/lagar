package app.lagar.ui.reader

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import com.mikepenz.markdown.compose.extendedspans.ExtendedSpans
import com.mikepenz.markdown.m3.Markdown
import com.mikepenz.markdown.m3.markdownColor
import com.mikepenz.markdown.m3.markdownTypography
import com.mikepenz.markdown.model.markdownAnnotator
import com.mikepenz.markdown.model.markdownExtendedSpans
import com.mikepenz.markdown.model.markdownPadding
import com.mikepenz.markdown.model.parseMarkdown
import org.intellij.markdown.MarkdownElementTypes
import org.intellij.markdown.ast.findChildOfType
import org.intellij.markdown.ast.getTextInNode

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
 *
 * Citations of the documents in [crossReferences] (id to the layer of the target) become links that
 * open [onOpenDocument]: text in the target layer's `onTint` color with a dotted underline. The text is
 * rewritten and parsed again only when the content or the resolved targets change.
 */
@Composable
internal fun LegalMarkdown(
    content: String,
    modifier: Modifier = Modifier,
    crossReferences: Map<String, LayerKey> = emptyMap(),
    onOpenDocument: (String) -> Unit = {},
) {
    val type = LagarTheme.type
    val colors = LagarTheme.colors
    val layers = LagarTheme.layers
    val source = remember(content, crossReferences) { linkCitations(content, crossReferences.keys) }
    val hasLinks = source !== content
    val state = remember(source) { parseMarkdown(source) }
    val open by rememberUpdatedState(onOpenDocument)
    val annotator = remember(type, layers, crossReferences) {
        markdownAnnotator { text, node ->
            when (node.type) {
                MarkdownElementTypes.STRONG -> {
                    val inner = text.substring(node.startOffset, node.endOffset).removeSurrounding("**")
                    if (!inner.endsWith("§")) return@markdownAnnotator false
                    withStyle(type.statuteNum.toSpanStyle()) { append(inner) }
                    true
                }
                MarkdownElementTypes.INLINE_LINK -> {
                    val destination = node.findChildOfType(MarkdownElementTypes.LINK_DESTINATION)?.getTextInNode(text)?.toString()
                    val id = destination?.takeIf { it.startsWith(CROSS_REFERENCE_SCHEME) }?.removePrefix(CROSS_REFERENCE_SCHEME)
                    val layer = id?.let(crossReferences::get) ?: return@markdownAnnotator false
                    val label = node.findChildOfType(MarkdownElementTypes.LINK_TEXT)?.getTextInNode(text)?.toString()
                        ?.removePrefix("[")?.removeSuffix("]") ?: return@markdownAnnotator false
                    val link = LinkAnnotation.Clickable(
                        tag = CROSS_REFERENCE_TAG + id,
                        styles = TextLinkStyles(SpanStyle(color = layers.onTint(layer))),
                        linkInteractionListener = { open(id) },
                    )
                    withLink(link) { append(label) }
                    true
                }
                else -> false
            }
        }
    }
    val extendedSpans = markdownExtendedSpans { remember { ExtendedSpans(DottedUnderlinePainter()) } }
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
        extendedSpans = if (hasLinks) extendedSpans else markdownExtendedSpans(),
        modifier = modifier,
    )
}

/**
 * One numbered statute (§), set flat in the running text like a page of a book: no card, no side bar. [action]
 * (the section menu) sits in the upper right corner, beside the text rather than over it.
 */
@Composable
internal fun StatuteContainer(
    modifier: Modifier = Modifier,
    action: (@Composable () -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    Row(modifier = modifier.fillMaxWidth()) {
        Box(Modifier.weight(1f).padding(vertical = LagarTheme.spacing.xs)) { content() }
        if (action != null) Box(Modifier.align(Alignment.Top)) { action() }
    }
}
