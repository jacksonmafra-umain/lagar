package app.lagar.ui.list

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp
import app.lagar.data.ListingItem
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.document_count
import app.lagar.resources.error_retry
import app.lagar.resources.error_title
import app.lagar.resources.layer_list_title
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.nameRes
import app.lagar.ui.common.rememberBackTopBarHeight
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/** Paginated list of the documents in one layer. */
@Composable
fun LayerListRoute(
    layer: String,
    type: String?,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    viewModel: LayerListViewModel = koinViewModel(key = "$layer/$type") { parametersOf(layer, type) },
) {
    val items by viewModel.items.collectAsState()
    val total by viewModel.total.collectAsState()
    val state by viewModel.state.collectAsState()
    val appending by viewModel.appending.collectAsState()
    val appendFailed by viewModel.appendFailed.collectAsState()
    LayerListScreen(
        layer = DisplayLayer.fromRoute(layer, type),
        items = items,
        total = total,
        state = state,
        appending = appending,
        appendFailed = appendFailed,
        onBack = onBack,
        onOpenDocument = onOpenDocument,
        onLoadNext = viewModel::loadNext,
        onRetryNext = viewModel::retryNext,
    )
}

@Composable
fun LayerListScreen(
    layer: DisplayLayer?,
    items: List<ListingItem>,
    total: Int?,
    state: LoadState<Unit>,
    appending: Boolean,
    appendFailed: Boolean,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    onLoadNext: () -> Unit,
    onRetryNext: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    val hazeState = remember { HazeState() }
    val listState = rememberLazyListState()
    var headerHeight by rememberBackTopBarHeight()
    val bottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    Box(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
        when (state) {
            LoadState.Loading -> Box(Modifier.fillMaxSize().padding(top = headerHeight), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            is LoadState.Failed -> Box(Modifier.fillMaxSize().padding(top = headerHeight), contentAlignment = Alignment.Center) {
                ErrorState(onRetry = state.retry)
            }
            is LoadState.Loaded -> {
                NearEndEffect(listState, items.size, onLoadNext)
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                    contentPadding = PaddingValues(
                        start = spacing.marginMobile,
                        end = spacing.marginMobile,
                        top = headerHeight + spacing.md,
                        bottom = bottomInset + spacing.md,
                    ),
                    verticalArrangement = Arrangement.spacedBy(spacing.sm),
                ) {
                    items(items, key = { it.id }) { StatuteRow(it, layer, onClick = { onOpenDocument(it.id) }) }
                    if (appending) {
                        item(key = "appending") {
                            Box(Modifier.fillMaxWidth().padding(spacing.md), contentAlignment = Alignment.Center) {
                                CircularProgressIndicator()
                            }
                        }
                    }
                    if (appendFailed) {
                        item(key = "append-failed") { AppendErrorRow(onRetryNext) }
                    }
                }
            }
        }
        ListHeader(
            layer = layer,
            total = total,
            hazeState = hazeState,
            onBack = onBack,
            onHeightChange = { headerHeight = it },
            modifier = Modifier.align(Alignment.TopCenter),
        )
    }
}

/** Asks for the next page when the last visible row is within [PREFETCH_DISTANCE] of the end. */
@Composable
private fun NearEndEffect(listState: LazyListState, itemCount: Int, onLoadNext: () -> Unit) {
    val currentCount by rememberUpdatedState(itemCount)
    val currentLoadNext by rememberUpdatedState(onLoadNext)
    LaunchedEffect(listState) {
        snapshotFlow { listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: -1 }
            .filter { it >= currentCount - PREFETCH_DISTANCE }
            .distinctUntilChanged()
            .collect { currentLoadNext() }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ListHeader(
    layer: DisplayLayer?,
    total: Int?,
    hazeState: HazeState,
    onBack: () -> Unit,
    onHeightChange: (Dp) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    BackTopBar(hazeState, onBack, onHeightChange, modifier) {
        FlowRow(
            modifier = Modifier.weight(1f),
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
            itemVerticalAlignment = Alignment.CenterVertically,
        ) {
            if (layer != null) {
                LayerBadge(layer, stringResource(layer.nameRes()))
            } else {
                Text(stringResource(Res.string.layer_list_title), style = LagarTheme.type.headlineSm, color = colors.onSurface)
            }
            if (total != null) {
                Text(
                    pluralStringResource(Res.plurals.document_count, total, total),
                    style = LagarTheme.type.labelSm,
                    color = colors.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun AppendErrorRow(onRetry: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            stringResource(Res.string.error_title),
            style = LagarTheme.type.bodyUi,
            color = LagarTheme.colors.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        TextButton(onClick = onRetry) { Text(stringResource(Res.string.error_retry)) }
    }
}

private const val PREFETCH_DISTANCE = 5
