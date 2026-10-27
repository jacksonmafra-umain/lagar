package app.lagar.ui.reader

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.data.DocumentResponse
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.ic_arrow_back
import app.lagar.resources.navigate_back
import app.lagar.ui.common.ErrorState
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
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
    var barPx by remember { mutableStateOf(0) }
    val barHeight = with(LocalDensity.current) { barPx.toDp() }
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
                val sections = remember(document.body) { splitSections(document.body) }
                LazyColumn(
                    modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                    contentPadding = PaddingValues(top = barHeight + spacing.md, bottom = bottomInset + spacing.lg),
                ) {
                    item(key = "header") {
                        Box(Modifier.fillMaxWidth().padding(horizontal = spacing.marginMobile), contentAlignment = Alignment.TopCenter) {
                            MetadataHeader(document.meta, Modifier.readingColumn())
                        }
                    }
                    itemsIndexed(sections, key = { index, _ -> index }) { index, section ->
                        Box(Modifier.fillMaxWidth().padding(horizontal = spacing.marginMobile), contentAlignment = Alignment.TopCenter) {
                            SelectionContainer(Modifier.readingColumn()) {
                                LegalMarkdown(if (index == 0) withoutTitle(section) else section)
                            }
                        }
                    }
                }
            }
        }
        ReaderBar(
            title = (state as? LoadState.Loaded)?.value?.meta?.number,
            hazeState = hazeState,
            onBack = onBack,
            modifier = Modifier.align(Alignment.TopCenter).onSizeChanged { barPx = it.height },
        )
    }
}

@Composable
private fun ReaderBar(title: String?, hazeState: HazeState, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val colors = LagarTheme.colors
    Row(
        modifier = modifier
            .fillMaxWidth()
            .glass(GlassTier.Bar, hazeState)
            .windowInsetsPadding(WindowInsets.statusBars)
            .heightIn(min = 64.dp)
            .padding(horizontal = LagarTheme.spacing.gutterMobile),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        val backDescription = stringResource(Res.string.navigate_back)
        Box(
            modifier = Modifier
                .size(48.dp)
                .clip(CircleShape)
                .clickable(role = Role.Button, onClick = onBack)
                .semantics { contentDescription = backDescription },
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(Res.drawable.ic_arrow_back), contentDescription = null, tint = colors.onSurfaceVariant)
        }
        if (title != null) {
            Text(
                text = title,
                style = LagarTheme.type.codeCitation,
                color = colors.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}
