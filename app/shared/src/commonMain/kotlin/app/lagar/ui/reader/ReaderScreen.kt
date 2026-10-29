package app.lagar.ui.reader

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import app.lagar.data.DocumentMeta
import app.lagar.data.DocumentResponse
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.bookmark_add
import app.lagar.resources.bookmark_remove
import app.lagar.resources.ic_bookmark
import app.lagar.resources.ic_bookmark_filled
import app.lagar.resources.ic_link
import app.lagar.resources.ic_share
import app.lagar.resources.ic_toc
import app.lagar.resources.reader_link_copied
import app.lagar.resources.reader_share_failed
import app.lagar.resources.reader_share_link
import app.lagar.resources.reader_toc
import app.lagar.settings.BookmarkStore
import app.lagar.settings.toBookmark
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.navigation.readerLink
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.launch
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/** Reads one document: metadata header, amendments, then the body one chapter or § per lazy item. */
@Composable
fun ReaderRoute(
    id: String,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    anchor: String? = null,
    viewModel: ReaderViewModel = koinViewModel(key = id) { parametersOf(id) },
    store: BookmarkStore = koinInject(),
) {
    val state by viewModel.state.collectAsState()
    val bookmarks by store.bookmarks.collectAsState()
    val links by viewModel.linkedAmendments.collectAsState()
    // Bookmarks saved before the dates were stored (or before a repeal) catch up when the document is read.
    LaunchedEffect(state) { (state as? LoadState.Loaded)?.value?.meta?.let { store.refresh(it.toBookmark()) } }
    ReaderScreen(
        state = state,
        bookmarked = bookmarks.any { it.id == id },
        onToggleBookmark = { meta -> store.toggle(meta.toBookmark()) },
        onBack = onBack,
        anchor = anchor,
        amendmentLinks = links,
        onResolveAmendmentLinks = viewModel::resolveAmendmentLinks,
        onOpenDocument = onOpenDocument,
    )
}

@Composable
fun ReaderScreen(
    state: LoadState<DocumentResponse>,
    bookmarked: Boolean,
    onToggleBookmark: (DocumentMeta) -> Unit,
    onBack: () -> Unit,
    anchor: String? = null,
    amendmentLinks: Map<String, String> = emptyMap(),
    onResolveAmendmentLinks: (List<String>) -> Unit = {},
    onOpenDocument: (String) -> Unit = {},
) {
    val spacing = LagarTheme.spacing
    val hazeState = remember { HazeState() }
    var barHeight by rememberBackTopBarHeight()
    val bottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    val sharer = rememberLinkSharer()
    val copied = stringResource(Res.string.reader_link_copied)
    val failed = stringResource(Res.string.reader_share_failed)
    var showToc by rememberSaveable { mutableStateOf(false) }
    var amendmentsOpen by rememberSaveable { mutableStateOf(false) }

    fun share(title: String, url: String) {
        when (sharer.share(title, url)) {
            ShareOutcome.Opened -> Unit
            ShareOutcome.Copied -> scope.launch { snackbar.showSnackbar(copied) }
            ShareOutcome.Failed -> scope.launch { snackbar.showSnackbar(failed) }
        }
    }

    val document = (state as? LoadState.Loaded)?.value
    val blocks = remember(document?.body) { document?.body?.let(::readerBlocks).orEmpty() }
    val outline = remember(blocks) { buildOutline(blocks) }
    val amendments = remember(document?.meta) { document?.meta?.let(::amendmentRows).orEmpty() }
    val reprints = document?.meta?.reprintedBy.orEmpty()
    val hasAmendments = amendments.isNotEmpty() || reprints.isNotEmpty()
    // Lazy items before the first block: the header, then the amendments toggle, the open list and a divider.
    val leadingItems = 1 + (if (hasAmendments) 2 else 0) +
        (if (hasAmendments && amendmentsOpen) amendments.size + (if (reprints.isNotEmpty()) 1 else 0) else 0)

    // A deep link scrolls to its section once, when the text has loaded; later recompositions leave the scroll alone.
    var anchorDone by rememberSaveable(anchor) { mutableStateOf(anchor == null) }
    LaunchedEffect(outline, anchor) {
        if (anchorDone || blocks.isEmpty() || anchor == null) return@LaunchedEffect
        outline.blockOf(anchor)?.let { listState.scrollToItem(leadingItems + it) }
        anchorDone = true
    }
    LaunchedEffect(amendmentsOpen, amendments, reprints) {
        if (amendmentsOpen) onResolveAmendmentLinks(amendments.map { it.number } + reprints)
    }

    Box(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
        when (state) {
            LoadState.Loading -> Box(Modifier.fillMaxSize().padding(top = barHeight), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            is LoadState.Failed -> Box(Modifier.fillMaxSize().padding(top = barHeight), contentAlignment = Alignment.Center) {
                ErrorState(onRetry = state.retry)
            }
            is LoadState.Loaded -> {
                val meta = state.value.meta
                val key = remember(meta) {
                    if (meta.repealed != null) LayerKey.Repealed
                    else DisplayLayer.fromRoute(meta.layer, meta.type)?.key ?: LayerKey.Repealed
                }
                val shareBase = remember { shareBaseUrl() }
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                    contentPadding = PaddingValues(top = barHeight + spacing.md, bottom = bottomInset + spacing.lg),
                ) {
                    item(key = "header") {
                        ReadingItem { MetadataHeader(meta, Modifier.readingColumn()) }
                    }
                    if (hasAmendments) {
                        item(key = "amendments") {
                            ReadingItem {
                                AmendmentsToggle(amendments.size, amendmentsOpen, { amendmentsOpen = !amendmentsOpen }, Modifier.readingColumn())
                            }
                        }
                        if (amendmentsOpen) {
                            if (reprints.isNotEmpty()) {
                                item(key = "reprints") {
                                    ReadingItem { ReprintsItem(reprints, amendmentLinks, key, onOpenDocument, Modifier.readingColumn()) }
                                }
                            }
                            itemsIndexed(amendments, key = { index, _ -> "amendment-$index" }) { _, row ->
                                ReadingItem {
                                    AmendmentItem(row, amendmentLinks[row.number], key, onOpenDocument, Modifier.readingColumn())
                                }
                            }
                        }
                        item(key = "amendments-end") {
                            ReadingItem {
                                HorizontalDivider(Modifier.readingColumn().padding(vertical = spacing.xs), color = LagarTheme.colors.outlineVariant)
                            }
                        }
                    }
                    itemsIndexed(blocks, key = { index, _ -> index }) { index, block ->
                        Box(
                            Modifier.fillMaxWidth().padding(horizontal = spacing.marginMobile, vertical = spacing.xs),
                            contentAlignment = Alignment.TopCenter,
                        ) {
                            SelectionContainer(Modifier.readingColumn()) {
                                if (isStatuteBlock(block)) {
                                    val blockAnchor = outline.anchorOf(index)
                                    val label = outline.labelOf(index)
                                    StatuteContainer(
                                        layer = key,
                                        action = if (blockAnchor != null && label != null) {
                                            { SectionLinkButton(label) { share("$label ${meta.title}", readerLink(shareBase, meta.id, blockAnchor)) } }
                                        } else {
                                            null
                                        },
                                    ) { LegalMarkdown(block.trimEnd()) }
                                } else if (block.startsWith("#")) {
                                    LegalMarkdown(block.trimEnd(), Modifier.semantics { heading() })
                                } else {
                                    LegalMarkdown(block.trimEnd())
                                }
                            }
                        }
                    }
                }
                if (showToc) {
                    TableOfContentsSheet(
                        outline = outline,
                        layer = key,
                        onSelect = { block ->
                            showToc = false
                            scope.launch { listState.scrollToItem(leadingItems + block) }
                        },
                        onDismiss = { showToc = false },
                    )
                }
            }
        }
        BackTopBar(hazeState, onBack, onHeightChange = { barHeight = it }, modifier = Modifier.align(Alignment.TopCenter)) {
            val meta = document?.meta
            Text(
                text = meta?.number.orEmpty(),
                style = LagarTheme.type.codeCitation,
                color = LagarTheme.colors.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            if (meta != null) {
                if (!outline.isEmpty) {
                    BarAction(painterResource(Res.drawable.ic_toc), stringResource(Res.string.reader_toc)) { showToc = true }
                }
                val shareBase = remember { shareBaseUrl() }
                BarAction(painterResource(Res.drawable.ic_share), stringResource(Res.string.reader_share_link, meta.title)) {
                    share(meta.title, readerLink(shareBase, meta.id))
                }
                BookmarkAction(meta, bookmarked, onToggleBookmark)
            }
        }
        SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter).navigationBarsPadding())
    }
}

/** Centers one lazy item in the reading column with the screen margins. */
@Composable
private fun ReadingItem(content: @Composable () -> Unit) {
    Box(Modifier.fillMaxWidth().padding(horizontal = LagarTheme.spacing.marginMobile), contentAlignment = Alignment.TopCenter) {
        content()
    }
}

/** The per-§ link action in the card's upper right corner; shares a deep link to that §. */
@Composable
private fun SectionLinkButton(label: String, onClick: () -> Unit) {
    BarAction(painterResource(Res.drawable.ic_link), stringResource(Res.string.reader_share_link, label), ShellDimens.SmallIconSize, onClick)
}

/** A 48dp round icon button in the reader's quiet style. */
@Composable
private fun BarAction(icon: Painter, description: String, iconSize: Dp = ShellDimens.IconSize, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = LagarTheme.colors.onSurfaceVariant, modifier = Modifier.size(iconSize))
    }
}

@Composable
private fun BookmarkAction(meta: DocumentMeta, bookmarked: Boolean, onToggle: (DocumentMeta) -> Unit) {
    val description = stringResource(if (bookmarked) Res.string.bookmark_remove else Res.string.bookmark_add, meta.title)
    val key = DisplayLayer.fromRoute(meta.layer, meta.type)?.key ?: LayerKey.SfsAct
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button) { onToggle(meta) }
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painterResource(if (bookmarked) Res.drawable.ic_bookmark_filled else Res.drawable.ic_bookmark),
            contentDescription = null,
            tint = if (bookmarked) LagarTheme.layers.onTint(key) else LagarTheme.colors.onSurfaceVariant,
        )
    }
}
