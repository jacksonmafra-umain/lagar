package app.lagar.ui.list

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.rememberScrollState
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
import app.lagar.designsystem.generated.LayerKey
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.document_count
import app.lagar.resources.error_retry
import app.lagar.resources.error_title
import app.lagar.resources.ic_info
import app.lagar.resources.layer_list_all_series
import app.lagar.resources.layer_list_empty_text
import app.lagar.resources.layer_list_empty_title
import app.lagar.resources.layer_list_title
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.PillTab
import app.lagar.ui.common.iconRes
import app.lagar.ui.common.nameRes
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.common.typeNameRes
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/** Paginated list of the documents in one layer, with a switch between its series when it has several. */
@Composable
fun LayerListRoute(
    layer: String,
    type: String?,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    ministry: MinistryFilter? = null,
    locality: LocalityFilter? = null,
    viewModel: LayerListViewModel = koinViewModel(key = "$layer/$type/${ministry?.id}/${locality?.code}") {
        parametersOf(layer, type, ministry, locality)
    },
) {
    val items by viewModel.items.collectAsState()
    val total by viewModel.total.collectAsState()
    val state by viewModel.state.collectAsState()
    val appending by viewModel.appending.collectAsState()
    val appendFailed by viewModel.appendFailed.collectAsState()
    val series by viewModel.series.collectAsState()
    val selectedType by viewModel.selectedType.collectAsState()
    LayerListScreen(
        apiLayer = layer,
        routeType = type,
        filterName = ministry?.name ?: locality?.name,
        series = series,
        selectedType = selectedType,
        items = items,
        total = total,
        state = state,
        appending = appending,
        appendFailed = appendFailed,
        onBack = onBack,
        onOpenDocument = onOpenDocument,
        onLoadNext = viewModel::loadNext,
        onRetryNext = viewModel::retryNext,
        onSelectSeries = viewModel::selectSeries,
    )
}

@Composable
fun LayerListScreen(
    apiLayer: String,
    routeType: String?,
    filterName: String?,
    series: List<String>,
    selectedType: String?,
    items: List<ListingItem>,
    total: Int?,
    state: LoadState<Unit>,
    appending: Boolean,
    appendFailed: Boolean,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    onLoadNext: () -> Unit,
    onRetryNext: () -> Unit,
    onSelectSeries: (String?) -> Unit,
) {
    val spacing = LagarTheme.spacing
    val hazeState = remember { HazeState() }
    // A new series starts at the top.
    val listState = remember(selectedType) { LazyListState() }
    val layer = DisplayLayer.fromRoute(apiLayer, selectedType)
    // The colour of the level the screen was opened on, for the "all" tab and untyped series.
    val baseKey = (DisplayLayer.fromRoute(apiLayer, routeType) ?: DisplayLayer.entries.firstOrNull { it.apiLayer == apiLayer })
        ?.key ?: LayerKey.Repealed
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
            is LoadState.Loaded -> if (items.isEmpty()) {
                Box(Modifier.fillMaxSize().padding(top = headerHeight, bottom = bottomInset), contentAlignment = Alignment.Center) {
                    EmptyState(
                        icon = layer?.iconRes() ?: Res.drawable.ic_info,
                        title = stringResource(Res.string.layer_list_empty_title),
                        text = stringResource(Res.string.layer_list_empty_text),
                    )
                }
            } else {
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
                    items(items, key = { it.id }) {
                        // On "all", each row takes the colour of its own series.
                        val rowLayer = DisplayLayer.fromRoute(apiLayer, it.type) ?: layer
                        StatuteRow(it, rowLayer, onClick = { onOpenDocument(it.id) })
                    }
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
            filterName = filterName,
            selectedType = selectedType,
            series = series,
            baseKey = baseKey,
            apiLayer = apiLayer,
            onSelectSeries = onSelectSeries,
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
    filterName: String?,
    selectedType: String?,
    series: List<String>,
    baseKey: LayerKey,
    apiLayer: String,
    onSelectSeries: (String?) -> Unit,
    total: Int?,
    hazeState: HazeState,
    onBack: () -> Unit,
    onHeightChange: (Dp) -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    BackTopBar(hazeState, onBack, onHeightChange, modifier) {
        Column(Modifier.weight(1f)) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
                verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                when {
                    layer != null -> LayerBadge(layer, stringResource(layer.nameRes()))
                    selectedType != null -> Text(stringResource(typeNameRes(selectedType)), style = LagarTheme.type.headlineSm, color = colors.onSurface)
                    else -> Text(stringResource(Res.string.layer_list_title), style = LagarTheme.type.headlineSm, color = colors.onSurface)
                }
                if (total != null) {
                    Text(
                        pluralStringResource(Res.plurals.document_count, total, total),
                        style = LagarTheme.type.labelSm,
                        color = colors.onSurfaceVariant,
                    )
                }
            }
            if (filterName != null) {
                Text(filterName, style = LagarTheme.type.headlineSm, color = colors.onSurface)
            }
            if (series.size > 1) {
                SeriesSwitch(apiLayer, series, selectedType, baseKey, onSelectSeries)
            }
        }
    }
}

/** "All" followed by one tab per series, each filled with its level's colour when selected. */
@Composable
private fun SeriesSwitch(
    apiLayer: String,
    series: List<String>,
    selectedType: String?,
    baseKey: LayerKey,
    onSelect: (String?) -> Unit,
) {
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        PillTab(
            text = stringResource(Res.string.layer_list_all_series),
            selected = selectedType == null,
            key = baseKey,
            onClick = { onSelect(null) },
        )
        series.forEach { type ->
            PillTab(
                text = stringResource(typeNameRes(type)),
                selected = selectedType == type,
                key = DisplayLayer.fromRoute(apiLayer, type)?.key ?: baseKey,
                onClick = { onSelect(type) },
            )
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
