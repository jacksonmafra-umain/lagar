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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
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
import app.lagar.settings.Bookmark
import app.lagar.settings.BookmarkStore
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/** Reads one document: metadata header, then the body one chapter per lazy item. */
@Composable
fun ReaderRoute(
    id: String,
    onBack: () -> Unit,
    viewModel: ReaderViewModel = koinViewModel(key = id) { parametersOf(id) },
    store: BookmarkStore = koinInject(),
) {
    val state by viewModel.state.collectAsState()
    val bookmarks by store.bookmarks.collectAsState()
    ReaderScreen(
        state = state,
        bookmarked = bookmarks.any { it.id == id },
        onToggleBookmark = { meta -> store.toggle(Bookmark(meta.id, meta.title, meta.number, meta.type, meta.layer)) },
        onBack = onBack,
    )
}

@Composable
fun ReaderScreen(
    state: LoadState<DocumentResponse>,
    bookmarked: Boolean,
    onToggleBookmark: (DocumentMeta) -> Unit,
    onBack: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    val hazeState = remember { HazeState() }
    var barHeight by rememberBackTopBarHeight()
    val bottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    Box(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
        when (state) {
            LoadState.Loading -> Box(Modifier.fillMaxSize().padding(top = barHeight), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            is LoadState.Failed -> Box(Modifier.fillMaxSize().padding(top = barHeight), contentAlignment = Alignment.Center) {
                ErrorState(onRetry = state.retry)
            }
            is LoadState.Loaded -> {
                val document = state.value
                val blocks = remember(document.body) {
                    var firstSection = true
                    splitSections(document.body).flatMap { section ->
                        splitParagraphs(if (firstSection) withoutTitle(section) else section).also { firstSection = false }
                    }.filter { it.isNotBlank() }
                }
                val layer = remember(document.meta) { DisplayLayer.fromRoute(document.meta.layer, document.meta.type) }
                LazyColumn(
                    modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                    contentPadding = PaddingValues(top = barHeight + spacing.md, bottom = bottomInset + spacing.lg),
                ) {
                    item(key = "header") {
                        Box(Modifier.fillMaxWidth().padding(horizontal = spacing.marginMobile), contentAlignment = Alignment.TopCenter) {
                            MetadataHeader(document.meta, Modifier.readingColumn())
                        }
                    }
                    itemsIndexed(blocks, key = { index, _ -> index }) { _, block ->
                        Box(
                            Modifier.fillMaxWidth().padding(horizontal = spacing.marginMobile, vertical = spacing.xs),
                            contentAlignment = Alignment.TopCenter,
                        ) {
                            SelectionContainer(Modifier.readingColumn()) {
                                if (isStatuteBlock(block)) {
                                    StatuteContainer(layer?.key ?: LayerKey.Repealed) { LegalMarkdown(block.trimEnd()) }
                                } else {
                                    LegalMarkdown(block.trimEnd())
                                }
                            }
                        }
                    }
                }
            }
        }
        BackTopBar(hazeState, onBack, onHeightChange = { barHeight = it }, modifier = Modifier.align(Alignment.TopCenter)) {
            val meta = (state as? LoadState.Loaded)?.value?.meta
            Text(
                text = meta?.number.orEmpty(),
                style = LagarTheme.type.codeCitation,
                color = LagarTheme.colors.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            if (meta != null) BookmarkAction(meta, bookmarked, onToggleBookmark)
        }
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
