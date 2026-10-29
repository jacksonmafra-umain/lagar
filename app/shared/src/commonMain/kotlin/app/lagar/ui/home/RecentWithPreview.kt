package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.data.DocumentMeta
import app.lagar.data.ListingItem
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.bookmark_add
import app.lagar.resources.bookmark_remove
import app.lagar.resources.coming_soon
import app.lagar.resources.feed_amended_through
import app.lagar.resources.home_favourites_empty_text
import app.lagar.resources.home_favourites_empty_title
import app.lagar.resources.home_show_more
import app.lagar.resources.home_tab_favourites
import app.lagar.resources.home_tab_recent
import app.lagar.resources.ic_arrow_forward
import app.lagar.resources.ic_bookmark
import app.lagar.resources.ic_bookmark_filled
import app.lagar.resources.ic_bookmarks
import app.lagar.resources.ic_info
import app.lagar.resources.type_number
import app.lagar.resources.wide_preview_continue
import app.lagar.resources.wide_preview_empty
import app.lagar.resources.wide_preview_open
import app.lagar.settings.Bookmark
import app.lagar.settings.BookmarkStore
import app.lagar.settings.toBookmark
import app.lagar.settings.toListingItem
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.PillTab
import app.lagar.ui.common.RepealedBadge
import app.lagar.ui.common.typeNameRes
import app.lagar.ui.reader.LegalMarkdown
import app.lagar.ui.reader.MetadataHeader
import app.lagar.ui.reader.ReaderViewModel
import app.lagar.ui.reader.StatuteContainer
import app.lagar.ui.reader.isStatuteBlock
import app.lagar.ui.reader.splitParagraphs
import app.lagar.ui.reader.splitSections
import app.lagar.ui.reader.withoutTitle
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

private enum class ListTab { Recent, Favourites }

/** Paragraphs of the document shown in the preview before "Continue reading". */
private const val PREVIEW_BLOCKS = 6

/**
 * The wide home's document area: newest documents or bookmarks on the left; selecting one shows its opening
 * text on the right. The first document is previewed until another is chosen. Region and Kommun list the chosen
 * locality's documents, or say why there are none.
 */
@Composable
internal fun RecentWithPreview(
    data: HomeData,
    bookmarks: List<Bookmark>,
    onOpenDocument: (String) -> Unit,
    onShowMore: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    if (data.scope != Scope.Nationell && data.localityHome == null) {
        LocalityEmptyState(data)
        return
    }
    var tab by rememberSaveable { mutableStateOf(ListTab.Recent) }
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    val items = when (tab) {
        ListTab.Recent -> data.recent
        ListTab.Favourites -> bookmarks.map { it.toListingItem() }
    }
    val previewId = selectedId?.takeIf { id -> items.any { it.id == id } } ?: items.firstOrNull()?.id
    Row(horizontalArrangement = Arrangement.spacedBy(spacing.lg), verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(0.42f), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
            Row(horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                ListTab.entries.forEach { entry ->
                    PillTab(
                        text = stringResource(if (entry == ListTab.Recent) Res.string.home_tab_recent else Res.string.home_tab_favourites),
                        selected = tab == entry,
                        key = data.scope.key,
                        onClick = { tab = entry },
                    )
                }
            }
            if (tab == ListTab.Favourites && items.isEmpty()) {
                EmptyState(
                    icon = Res.drawable.ic_bookmarks,
                    title = stringResource(Res.string.home_favourites_empty_title),
                    text = stringResource(Res.string.home_favourites_empty_text),
                )
            }
            items.forEach { item -> DocumentRow(item, selected = item.id == previewId, onClick = { selectedId = item.id }) }
            if (tab == ListTab.Recent && data.hasMoreRecent) {
                OutlinedButton(onClick = onShowMore, modifier = Modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget)) {
                    Text(stringResource(Res.string.home_show_more))
                }
            }
        }
        Box(Modifier.weight(0.58f)) {
            if (previewId != null) {
                DocumentPreview(previewId, onOpenFull = onOpenDocument)
            } else {
                Text(stringResource(Res.string.wide_preview_empty), style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurfaceVariant)
            }
        }
    }
}

/** A compact, selectable document: type and number badge, status, title and the latest amendment. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DocumentRow(item: ListingItem, selected: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    val layers = LagarTheme.layers
    val spacing = LagarTheme.spacing
    val layer = item.displayLayer()
    val repealed = item.repealed != null
    val key = if (repealed) LayerKey.Repealed else (layer?.key ?: LayerKey.SfsAct)
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().semantics { this.selected = selected },
        shape = MaterialTheme.shapes.large,
        color = if (selected) layers.tint(key) else colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, if (selected) layers.accent(key) else colors.outlineVariant),
    ) {
        Column(Modifier.padding(spacing.md), verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                verticalArrangement = Arrangement.spacedBy(spacing.xs),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                val label = layer?.let { stringResource(Res.string.type_number, stringResource(typeNameRes(item.type)), item.number) } ?: item.number
                LayerBadge(key, label)
                if (repealed) RepealedBadge() else InForce()
            }
            Text(
                item.title,
                style = LagarTheme.type.bodyUi,
                fontWeight = FontWeight.SemiBold,
                color = if (repealed) colors.onSurfaceVariant else colors.onSurface,
                textDecoration = if (repealed) TextDecoration.LineThrough else null,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            item.amendedThrough?.let {
                Text(stringResource(Res.string.feed_amended_through, it), style = LagarTheme.type.labelSm, color = layers.onTint(key))
            }
        }
    }
}

/** The document's header and opening paragraphs, with bookmark and "Open full text"; loads like the reader. */
@Composable
private fun DocumentPreview(
    id: String,
    onOpenFull: (String) -> Unit,
    viewModel: ReaderViewModel = koinViewModel(key = "preview-$id") { parametersOf(id) },
    store: BookmarkStore = koinInject(),
) {
    val colors = LagarTheme.colors
    val spacing = LagarTheme.spacing
    val state by viewModel.state.collectAsState()
    val bookmarks by store.bookmarks.collectAsState()
    LaunchedEffect(state) { (state as? LoadState.Loaded)?.value?.meta?.let { store.refresh(it.toBookmark()) } }
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, colors.outlineVariant),
    ) {
        when (val s = state) {
            LoadState.Loading -> Box(Modifier.fillMaxWidth().heightIn(min = 240.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            is LoadState.Failed -> Box(Modifier.fillMaxWidth().padding(spacing.lg), contentAlignment = Alignment.Center) {
                ErrorState(onRetry = s.retry)
            }
            is LoadState.Loaded -> {
                val document = s.value
                val blocks = remember(document.body) {
                    var first = true
                    splitSections(document.body).flatMap { section ->
                        splitParagraphs(if (first) withoutTitle(section) else section).also { first = false }
                    }.filter { it.isNotBlank() }
                }
                val key = if (document.meta.repealed != null) {
                    LayerKey.Repealed
                } else {
                    DisplayLayer.fromRoute(document.meta.layer, document.meta.type)?.key ?: LayerKey.SfsAct
                }
                Column(Modifier.padding(spacing.lg), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                        MetadataHeader(document.meta, Modifier.weight(1f))
                        PreviewActions(document.meta, bookmarks.any { it.id == id }, onToggleBookmark = { store.toggle(document.meta.toBookmark()) }) {
                            onOpenFull(id)
                        }
                    }
                    SelectionContainer {
                        Column(verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                            blocks.take(PREVIEW_BLOCKS).forEach { block ->
                                if (isStatuteBlock(block)) StatuteContainer(key) { LegalMarkdown(block.trimEnd()) } else LegalMarkdown(block.trimEnd())
                            }
                        }
                    }
                    if (blocks.size > PREVIEW_BLOCKS) {
                        TextButton(onClick = { onOpenFull(id) }) {
                            Text(stringResource(Res.string.wide_preview_continue), style = LagarTheme.type.labelMd)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PreviewActions(meta: DocumentMeta, bookmarked: Boolean, onToggleBookmark: () -> Unit, onOpenFull: () -> Unit) {
    val colors = LagarTheme.colors
    val key = DisplayLayer.fromRoute(meta.layer, meta.type)?.key ?: LayerKey.SfsAct
    val description = stringResource(if (bookmarked) Res.string.bookmark_remove else Res.string.bookmark_add, meta.title)
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
        Surface(
            onClick = onToggleBookmark,
            shape = CircleShape,
            color = colors.surfaceContainerLowest,
            modifier = Modifier.size(ShellDimens.TouchTarget).semantics { contentDescription = description },
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(
                    painterResource(if (bookmarked) Res.drawable.ic_bookmark_filled else Res.drawable.ic_bookmark),
                    contentDescription = null,
                    tint = if (bookmarked) LagarTheme.layers.onTint(key) else colors.onSurfaceVariant,
                )
            }
        }
        Surface(onClick = onOpenFull, shape = CircleShape, color = colors.primary) {
            Row(
                modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).padding(horizontal = LagarTheme.spacing.md),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
            ) {
                Text(stringResource(Res.string.wide_preview_open), style = LagarTheme.type.labelMd, fontWeight = FontWeight.Bold, color = colors.onPrimary)
                Icon(painterResource(Res.drawable.ic_arrow_forward), null, tint = colors.onPrimary, modifier = Modifier.size(ShellDimens.SmallIconSize))
            }
        }
    }
}
