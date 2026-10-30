package app.lagar.ui.reader

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.VerticalDivider
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
import androidx.compose.ui.text.font.FontWeight
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
import app.lagar.resources.ic_info
import app.lagar.resources.ic_share
import app.lagar.resources.ic_toc
import app.lagar.resources.reader_inspector
import app.lagar.resources.reader_inspector_open
import app.lagar.resources.reader_link_copied
import app.lagar.resources.reader_provision_removed
import app.lagar.resources.reader_provision_saved
import app.lagar.resources.reader_share_failed
import app.lagar.resources.reader_share_link
import app.lagar.resources.reader_toc
import app.lagar.settings.BookmarkStore
import app.lagar.settings.NoteStore
import app.lagar.settings.SavedProvision
import app.lagar.settings.toBookmark
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.navigation.readerLink
import app.lagar.ui.shell.LocalWideLayout
import app.lagar.ui.shell.ShellDimens
import app.lagar.ui.shell.wideListPadding
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.launch
import org.jetbrains.compose.resources.getString
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
    noteStore: NoteStore = koinInject(),
) {
    val state by viewModel.state.collectAsState()
    val bookmarks by store.bookmarks.collectAsState()
    val provisions by store.provisions.collectAsState()
    val notes by noteStore.notes.collectAsState()
    val savedAnchors = remember(provisions, id) { provisions.filter { it.document.id == id }.mapTo(HashSet()) { it.anchor } }
    val documentNotes = remember(notes, id) { notes.filter { it.document.id == id } }
    val provisionNotes = remember(documentNotes) { documentNotes.mapNotNull { note -> note.anchor?.let { it to note.text } }.toMap() }
    val links by viewModel.linkedAmendments.collectAsState()
    val cited by viewModel.crossReferences.collectAsState()
    // The layer colors a cross-reference; a type the app does not place falls back to SFS acts.
    val crossReferences = remember(cited) { cited.mapValues { (_, type) -> DisplayLayer.forType(type)?.key ?: LayerKey.SfsAct } }
    // Bookmarks saved before the dates were stored (or before a repeal) catch up when the document is read.
    LaunchedEffect(state) {
        (state as? LoadState.Loaded)?.value?.meta?.toBookmark()?.let {
            store.refresh(it)
            noteStore.refresh(it)
        }
    }
    ReaderScreen(
        state = state,
        bookmarked = bookmarks.any { it.id == id },
        onToggleBookmark = { meta -> store.toggle(meta.toBookmark()) },
        onBack = onBack,
        anchor = anchor,
        amendmentLinks = links,
        onResolveAmendmentLinks = viewModel::resolveAmendmentLinks,
        crossReferences = crossReferences,
        onOpenDocument = onOpenDocument,
        savedAnchors = savedAnchors,
        documentNote = documentNotes.firstOrNull { it.anchor == null }?.text,
        provisionNotes = provisionNotes,
        onToggleProvision = { meta, anchor, label, excerpt ->
            store.toggleProvision(SavedProvision(meta.toBookmark(), anchor, label, excerpt))
        },
        onWriteNote = { meta, anchor, label, text -> noteStore.write(meta.toBookmark(), anchor, label, text) },
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
    crossReferences: Map<String, LayerKey> = emptyMap(),
    onOpenDocument: (String) -> Unit = {},
    savedAnchors: Set<String> = emptySet(),
    documentNote: String? = null,
    provisionNotes: Map<String, String> = emptyMap(),
    onToggleProvision: (meta: DocumentMeta, anchor: String, label: String, excerpt: String) -> Unit = { _, _, _, _ -> },
    onWriteNote: (meta: DocumentMeta, anchor: String?, label: String?, text: String) -> Unit = { _, _, _, _ -> },
) = BoxWithConstraints(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
    val spacing = LagarTheme.spacing
    val wide = LocalWideLayout.current
    val inspector = wide && maxWidth >= ShellDimens.ReaderInspectorBreakpoint
    // Tablet widths (and desktop below the inspector breakpoint): the metadata slides in from a drawer instead.
    val drawer = !inspector && maxWidth >= ShellDimens.MediumBreakpoint
    // The facts and amendments sit beside the text, in the inspector pane or the drawer, not under the title.
    val sideFacts = inspector || drawer
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
    var drawerOpen by rememberSaveable { mutableStateOf(false) }
    // The note being edited: open with the anchor of its §, or no anchor for the document note.
    var noteOpen by rememberSaveable { mutableStateOf(false) }
    var noteAnchor by rememberSaveable { mutableStateOf<String?>(null) }

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
    // Lazy items before the first block: the header and the document note, then (unless the inspector or the drawer
    // holds them) the amendments toggle, the open list and a divider.
    val leadingItems = if (sideFacts) {
        2
    } else {
        2 + (if (hasAmendments) 2 else 0) +
            (if (hasAmendments && amendmentsOpen) amendments.size + (if (reprints.isNotEmpty()) 1 else 0) else 0)
    }
    val tocPane = wide && !outline.isEmpty

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

    when (state) {
        LoadState.Loading -> Box(Modifier.fillMaxSize().padding(top = barHeight), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        is LoadState.Failed -> Box(Modifier.fillMaxSize().padding(top = barHeight), contentAlignment = Alignment.Center) {
            ErrorState(onRetry = state.retry)
        }
        is LoadState.Loaded -> {
            val meta = state.value.meta
            val key = remember(meta) { readerLayer(meta) }
            val shareBase = remember { shareBaseUrl() }
            val sectionActions: @Composable (String, String, String) -> Unit = { anchor, label, block ->
                val saved = anchor in savedAnchors
                SectionActions(
                    label = label,
                    layer = key,
                    saved = saved,
                    hasNote = anchor in provisionNotes,
                    onToggleSave = {
                        onToggleProvision(meta, anchor, label, provisionExcerpt(block))
                        scope.launch {
                            snackbar.showSnackbar(
                                getString(if (saved) Res.string.reader_provision_removed else Res.string.reader_provision_saved, label),
                            )
                        }
                    },
                    onNote = {
                        noteAnchor = anchor
                        noteOpen = true
                    },
                    onShare = { share("$label ${meta.title}", readerLink(shareBase, meta.id, anchor)) },
                )
            }
            val noteChip: @Composable (String) -> Unit = { anchor ->
                provisionNotes[anchor]?.let { text ->
                    NoteChip(text, key, onEdit = {
                        noteAnchor = anchor
                        noteOpen = true
                    })
                }
            }
            val inspectorContent = @Composable {
                DocumentInspector(
                    meta = meta,
                    amendments = amendments,
                    reprints = reprints,
                    amendmentsOpen = amendmentsOpen,
                    onToggleAmendments = { amendmentsOpen = !amendmentsOpen },
                    amendmentLinks = amendmentLinks,
                    layer = key,
                    onOpenDocument = onOpenDocument,
                )
            }
            val text = @Composable { modifier: Modifier ->
                LazyColumn(
                    state = listState,
                    modifier = modifier,
                    contentPadding = PaddingValues(top = barHeight + spacing.md, bottom = bottomInset + spacing.lg),
                ) {
                    item(key = "header") {
                        ReadingItem {
                            if (sideFacts) {
                                Column(Modifier.readingColumn(), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                                    DocumentTitle(meta)
                                    HorizontalDivider(Modifier.padding(top = spacing.xs), color = LagarTheme.colors.outlineVariant)
                                }
                            } else {
                                MetadataHeader(meta, Modifier.readingColumn())
                            }
                        }
                    }
                    item(key = "document-note") {
                        ReadingItem {
                            Box(Modifier.readingColumn().padding(bottom = spacing.xs)) {
                                DocumentNote(documentNote, key, onEdit = {
                                    noteAnchor = null
                                    noteOpen = true
                                })
                            }
                        }
                    }
                    if (hasAmendments && !sideFacts) {
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
                                val blockAnchor = outline.anchorOf(index)
                                val label = outline.labelOf(index)
                                if (isStatuteBlock(block)) {
                                    // A § printed once per wording carries Riksdagen's marker, shown as a label.
                                    val statute = remember(block) { statuteValidity(block) }
                                    StatuteContainer(
                                        layer = key,
                                        action = if (blockAnchor != null && label != null) {
                                            { sectionActions(blockAnchor, label, statute.text) }
                                        } else {
                                            null
                                        },
                                    ) {
                                        Column(verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                                            statute.marker?.let { ValidityLabel(it, key) }
                                            LegalMarkdown(statute.text.trimEnd(), crossReferences = crossReferences, onOpenDocument = onOpenDocument)
                                            if (blockAnchor != null) noteChip(blockAnchor)
                                        }
                                    }
                                } else if (block.startsWith("#") && blockAnchor != null && label != null) {
                                    // A chapter heading: saved, noted and shared like a §.
                                    Column(verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                                        Row {
                                            LegalMarkdown(block.trimEnd(), Modifier.weight(1f).semantics { heading() })
                                            sectionActions(blockAnchor, label, block)
                                        }
                                        noteChip(blockAnchor)
                                    }
                                } else if (block.startsWith("#")) {
                                    LegalMarkdown(block.trimEnd(), Modifier.semantics { heading() })
                                } else {
                                    LegalMarkdown(block.trimEnd(), crossReferences = crossReferences, onOpenDocument = onOpenDocument)
                                }
                            }
                        }
                    }
                }
            }
            if (wide) {
                Row(
                    Modifier
                        .fillMaxSize()
                        .hazeSource(hazeState)
                        .padding(horizontal = wideListPadding(maxWidth, spacing.margin)),
                ) {
                    val paneTop = barHeight + spacing.md
                    if (tocPane) {
                        Column(Modifier.width(ShellDimens.ReaderPaneWidth).fillMaxHeight().padding(top = paneTop)) {
                            PaneHeading(stringResource(Res.string.reader_toc))
                            TableOfContentsList(
                                outline = outline,
                                layer = key,
                                onSelect = { block -> scope.launch { listState.scrollToItem(leadingItems + block) } },
                                contentPadding = PaddingValues(top = spacing.sm, end = spacing.md, bottom = bottomInset + spacing.lg),
                                modifier = Modifier.weight(1f),
                            )
                        }
                        VerticalDivider(Modifier.padding(top = paneTop), color = LagarTheme.colors.outlineVariant)
                    }
                    text(Modifier.weight(1f).fillMaxHeight())
                    if (inspector) {
                        VerticalDivider(Modifier.padding(top = paneTop), color = LagarTheme.colors.outlineVariant)
                        Column(
                            modifier = Modifier
                                .width(ShellDimens.ReaderPaneWidth)
                                .fillMaxHeight()
                                .verticalScroll(rememberScrollState())
                                .padding(start = spacing.md, top = paneTop, bottom = bottomInset + spacing.lg),
                            verticalArrangement = Arrangement.spacedBy(spacing.sm),
                        ) {
                            PaneHeading(stringResource(Res.string.reader_inspector))
                            inspectorContent()
                        }
                    }
                }
            } else {
                text(Modifier.fillMaxSize().hazeSource(hazeState))
            }
            if (noteOpen) {
                val anchor = noteAnchor
                val target = anchor?.let { a -> outline.blockOf(a)?.let(outline::labelOf) }
                val existing = if (anchor == null) documentNote else provisionNotes[anchor]
                NoteEditorSheet(
                    target = target ?: meta.title,
                    initial = existing.orEmpty(),
                    onSave = { text ->
                        onWriteNote(meta, anchor, target, text)
                        noteOpen = false
                    },
                    onDelete = if (existing != null) {
                        {
                            onWriteNote(meta, anchor, target, "")
                            noteOpen = false
                        }
                    } else {
                        null
                    },
                    onDismiss = { noteOpen = false },
                )
            }
            if (showToc && !tocPane) {
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
            if (!outline.isEmpty && !tocPane) {
                BarAction(painterResource(Res.drawable.ic_toc), stringResource(Res.string.reader_toc)) { showToc = true }
            }
            if (drawer) {
                BarAction(painterResource(Res.drawable.ic_info), stringResource(Res.string.reader_inspector_open)) { drawerOpen = true }
            }
            val shareBase = remember { shareBaseUrl() }
            BarAction(painterResource(Res.drawable.ic_share), stringResource(Res.string.reader_share_link, meta.title)) {
                share(meta.title, readerLink(shareBase, meta.id))
            }
            BookmarkAction(meta, bookmarked, onToggleBookmark)
        }
    }
    val loaded = (state as? LoadState.Loaded)?.value?.meta
    if (drawer && loaded != null) {
        InspectorDrawer(open = drawerOpen, hazeState = hazeState, onClose = { drawerOpen = false }) {
            DocumentInspector(
                meta = loaded,
                amendments = amendments,
                reprints = reprints,
                amendmentsOpen = amendmentsOpen,
                onToggleAmendments = { amendmentsOpen = !amendmentsOpen },
                amendmentLinks = amendmentLinks,
                layer = remember(loaded) { readerLayer(loaded) },
                onOpenDocument = {
                    drawerOpen = false
                    onOpenDocument(it)
                },
            )
        }
    }
    SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter).navigationBarsPadding())
}

/** The layer colour of a document in the reader: its layer's, or the repealed grey once it is repealed. */
private fun readerLayer(meta: DocumentMeta): LayerKey =
    if (meta.repealed != null) LayerKey.Repealed else DisplayLayer.fromRoute(meta.layer, meta.type)?.key ?: LayerKey.Repealed

/** Centers one lazy item in the reading column with the screen margins. */
@Composable
private fun ReadingItem(content: @Composable () -> Unit) {
    Box(Modifier.fillMaxWidth().padding(horizontal = LagarTheme.spacing.marginMobile), contentAlignment = Alignment.TopCenter) {
        content()
    }
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
