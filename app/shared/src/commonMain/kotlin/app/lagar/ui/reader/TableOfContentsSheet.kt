package app.lagar.ui.reader

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.reader_toc
import app.lagar.resources.reader_toc_go_to
import app.lagar.resources.reader_toc_preamble
import app.lagar.ui.common.SheetShape
import app.lagar.ui.common.sheetGlass
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.stringResource

/**
 * The document's chapters, each with its statutes as compact § chips. One lazy item per chapter keeps a
 * long code (Brottsbalken: 30-odd chapters, 600-odd §) cheap to open. [onSelect] gets the block index.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun TableOfContentsSheet(outline: Outline, layer: LayerKey, onSelect: (Int) -> Unit, onDismiss: () -> Unit) {
    val spacing = LagarTheme.spacing
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        modifier = Modifier.sheetGlass(SheetShape),
        shape = SheetShape,
        containerColor = Color.Transparent,
        contentColor = LagarTheme.colors.onSurface,
    ) {
        Text(
            text = stringResource(Res.string.reader_toc),
            style = LagarTheme.type.headlineMd,
            color = LagarTheme.colors.onSurface,
            modifier = Modifier.padding(horizontal = spacing.marginMobile).semantics { heading() },
        )
        TableOfContentsList(
            outline = outline,
            layer = layer,
            onSelect = onSelect,
            contentPadding = PaddingValues(start = spacing.marginMobile, end = spacing.marginMobile, top = spacing.sm, bottom = bottom + spacing.lg),
        )
    }
}

/** The chapters and their § chips; the body of [TableOfContentsSheet], and on desktop the pane beside the text. */
@Composable
internal fun TableOfContentsList(
    outline: Outline,
    layer: LayerKey,
    onSelect: (Int) -> Unit,
    contentPadding: PaddingValues,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier,
        contentPadding = contentPadding,
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
    ) {
        items(outline.chapters, key = { it.blockIndex }) { chapter ->
            ChapterEntry(chapter, layer, onSelect)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChapterEntry(chapter: OutlineChapter, layer: LayerKey, onSelect: (Int) -> Unit) {
    val spacing = LagarTheme.spacing
    val chapterNumber = chapter.title?.substringBefore(" kap.", missingDelimiterValue = "")?.let { if (it.isEmpty()) null else "$it kap." }
    Column(verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
        val title = chapter.title ?: stringResource(Res.string.reader_toc_preamble)
        val headingModifier = Modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget).semantics { heading() }
        Box(
            modifier = if (chapter.anchor != null) {
                headingModifier.clip(MaterialTheme.shapes.small).clickable(role = Role.Button) { onSelect(chapter.blockIndex) }
            } else {
                headingModifier
            },
            contentAlignment = Alignment.CenterStart,
        ) {
            Text(title, style = LagarTheme.type.headlineSm, color = LagarTheme.colors.onSurface)
        }
        if (chapter.statutes.isNotEmpty()) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing.xs), verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                // A provision with a pending new wording appears twice in the text; the chip jumps to the first.
                chapter.statutes.distinctBy { it.label }.forEach { statute ->
                    val name = if (chapterNumber != null) "$chapterNumber ${statute.label}" else statute.label
                    StatuteChip(statute.label, stringResource(Res.string.reader_toc_go_to, name), layer) { onSelect(statute.blockIndex) }
                }
            }
        }
    }
}

@Composable
private fun StatuteChip(label: String, description: String, layer: LayerKey, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    Box(
        modifier = Modifier
            .sizeIn(minWidth = ShellDimens.TouchTarget, minHeight = ShellDimens.TouchTarget)
            .clip(MaterialTheme.shapes.small)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = MaterialTheme.shapes.small,
            color = layers.tint(layer),
            border = BorderStroke(1.dp, layers.border(layer)),
        ) {
            Text(
                text = label,
                style = LagarTheme.type.labelMd.copy(fontWeight = FontWeight.Bold),
                color = layers.onTint(layer),
                modifier = Modifier.padding(horizontal = LagarTheme.spacing.sm, vertical = LagarTheme.spacing.xs),
            )
        }
    }
}
