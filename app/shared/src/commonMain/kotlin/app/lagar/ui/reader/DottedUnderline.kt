package app.lagar.ui.reader

import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import com.mikepenz.markdown.compose.extendedspans.ExtendedSpanPainter
import com.mikepenz.markdown.compose.extendedspans.SpanDrawInstructions

/** Tag of the clickable link annotations the reader puts on cross-references; the document id follows it. */
internal const val CROSS_REFERENCE_TAG = "lagar-xref:"

// Marks the ranges to underline; the item is the link color as ARGB.
private const val DOTTED_TAG = "lagar-dotted"

private val DotSize = 1.5.dp
private val DotGap = 2.dp
private val UnderlineOffset = 2.5.dp

/**
 * Draws the dotted underline DESIGN.md asks for under cross-references: Compose text decorations have
 * no dotted style, so the links carry no decoration and this painter draws round dots in the link's
 * color just below the baseline of each line the link covers.
 */
internal class DottedUnderlinePainter : ExtendedSpanPainter() {
    override fun decorate(span: SpanStyle, start: Int, end: Int, text: AnnotatedString, builder: AnnotatedString.Builder): SpanStyle = span

    override fun decorate(link: LinkAnnotation, start: Int, end: Int, text: AnnotatedString, builder: AnnotatedString.Builder): LinkAnnotation {
        if ((link as? LinkAnnotation.Clickable)?.tag?.startsWith(CROSS_REFERENCE_TAG) == true) {
            val color = link.styles?.style?.color ?: Color.Unspecified
            builder.addStringAnnotation(DOTTED_TAG, color.toArgb().toString(), start, end)
        }
        return link
    }

    override fun drawInstructionsFor(layoutResult: TextLayoutResult, color: Color?): SpanDrawInstructions {
        val text = layoutResult.layoutInput.text
        val ranges = text.getStringAnnotations(DOTTED_TAG, 0, text.length)
        if (ranges.isEmpty()) return NoInstructions
        val lines = ranges.flatMap { range ->
            val lineColor = Color(range.item.toInt())
            layoutResult.getBoundingBoxes(range.start, range.end).map { box ->
                val line = layoutResult.getLineForVerticalPosition(box.center.y)
                DottedLine(box.left, box.right, layoutResult.getLineBaseline(line), lineColor)
            }
        }
        return object : SpanDrawInstructions {
            override fun DrawScope.draw() = drawDots(lines)
        }
    }

    private fun DrawScope.drawDots(lines: List<DottedLine>) {
        val dot = DotSize.toPx()
        // A near-zero dash with round caps draws a dot; the gap sets the spacing between dot centers.
        val effect = PathEffect.dashPathEffect(floatArrayOf(0.01f, dot + DotGap.toPx()))
        lines.forEach { line ->
            val y = line.baseline + UnderlineOffset.toPx()
            drawLine(
                color = line.color,
                start = Offset(line.left + dot / 2, y),
                end = Offset(line.right, y),
                strokeWidth = dot,
                cap = StrokeCap.Round,
                pathEffect = effect,
            )
        }
    }

    private object NoInstructions : SpanDrawInstructions {
        override fun DrawScope.draw() = Unit
    }

    private class DottedLine(val left: Float, val right: Float, val baseline: Float, val color: Color)
}
