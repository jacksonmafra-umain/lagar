package app.lagar.ui.reader

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import app.lagar.data.DocumentResponse
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.rememberBackTopBarHeight
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/** Reads one document: metadata header, then the body one chapter per lazy item. */
@Composable
fun ReaderRoute(
    id: String,
    onBack: () -> Unit,
    viewModel: ReaderViewModel = koinViewModel(key = id) { parametersOf(id) },
) {
    val state by viewModel.state.collectAsState()
    ReaderScreen(state = state, onBack = onBack)
}

@Composable
fun ReaderScreen(state: LoadState<DocumentResponse>, onBack: () -> Unit) {
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
            (state as? LoadState.Loaded)?.value?.meta?.number?.let {
                Text(
                    text = it,
                    style = LagarTheme.type.codeCitation,
                    color = LagarTheme.colors.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}
