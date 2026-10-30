package app.lagar.ui.hierarki

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.i18n.documentCount
import app.lagar.resources.Res
import app.lagar.resources.explore_distribution_title
import app.lagar.resources.explore_layers_title
import app.lagar.resources.hierarchy_hint
import app.lagar.resources.hierarchy_view_layers
import app.lagar.resources.hierarchy_view_pyramid
import app.lagar.ui.common.ComingSoonSheet
import app.lagar.ui.common.LoadStateHost
import app.lagar.ui.common.PillTab
import app.lagar.ui.list.LayerListRoute
import app.lagar.ui.shell.LocalDetailPane
import app.lagar.ui.shell.ShellDimens
import app.lagar.ui.shell.maxContentWidth
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel

private enum class HierarkiView { Layers, Pyramid }

/**
 * Hierarki tab. [onOpenLayer] is called only for layers that have documents; [onBrowseByMinistry] only for
 * levels with a per-ministry index ([DisplayLayer.hasMinistryIndex]). On wide windows the layer's documents open in a
 * detail pane beside the list instead, and [onOpenDocument] opens one of them.
 */
@Composable
fun HierarkiRoute(
    onOpenLayer: (DisplayLayer) -> Unit,
    onBrowseByMinistry: (DisplayLayer) -> Unit,
    onOpenDocument: (String) -> Unit,
    viewModel: HierarkiViewModel = koinViewModel(),
) {
    val state by viewModel.state.collectAsState()
    var comingSoon by remember { mutableStateOf<DisplayLayer?>(null) }
    var selected by rememberSaveable { mutableStateOf<String?>(null) }
    HierarkiScreen(
        state = state,
        onLayerClick = { if (it.count > 0) onOpenLayer(it.layer) else comingSoon = it.layer },
        onBrowseByMinistry = { onBrowseByMinistry(it.layer) },
        selected = selected?.let { name -> DisplayLayer.entries.firstOrNull { it.name == name } },
        onSelectLayer = { if (it.count > 0) selected = it.layer.name else comingSoon = it.layer },
        detail = { layer ->
            LayerListRoute(layer = layer.apiLayer, type = layer.apiType, onBack = {}, onOpenDocument = onOpenDocument)
        },
    )
    comingSoon?.let { ComingSoonSheet(it) { comingSoon = null } }
}

/**
 * A "Lager" / "Pyramid" segmented switch above either the layer list or the norm pyramid. When [detail] is given and
 * the content is at least [ShellDimens.ListDetailMinWidth] wide, the list keeps [ShellDimens.ListPaneWidth] and the
 * [selected] layer (else the first with documents) shows in [detail] beside it; taps then go to [onSelectLayer].
 */
@Composable
fun HierarkiScreen(
    state: LoadState<List<LayerSummary>>,
    onLayerClick: (LayerSummary) -> Unit,
    onBrowseByMinistry: (LayerSummary) -> Unit = {},
    selected: DisplayLayer? = null,
    onSelectLayer: (LayerSummary) -> Unit = onLayerClick,
    detail: (@Composable (DisplayLayer) -> Unit)? = null,
) {
    val spacing = LagarTheme.spacing
    var view by rememberSaveable { mutableStateOf(HierarkiView.Layers) }
    LoadStateHost(state) { summaries, shell ->
        BoxWithConstraints(Modifier.fillMaxSize().maxContentWidth()) {
            val open = selected ?: summaries.firstOrNull { it.count > 0 }?.layer
            if (detail != null && open != null && maxWidth >= ShellDimens.ListDetailMinWidth) {
                Row(Modifier.fillMaxSize()) {
                    LayerPane(
                        summaries = summaries,
                        view = view,
                        onViewChange = { view = it },
                        shell = shell,
                        onLayerClick = onSelectLayer,
                        onBrowseByMinistry = onBrowseByMinistry,
                        selected = open,
                        modifier = Modifier.width(ShellDimens.ListPaneWidth),
                    )
                    Box(
                        Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .padding(
                                top = shell.calculateTopPadding() + spacing.sm,
                                bottom = shell.calculateBottomPadding() + spacing.md,
                                end = spacing.marginMobile,
                            )
                            .clip(MaterialTheme.shapes.large),
                    ) {
                        CompositionLocalProvider(LocalDetailPane provides true) {
                            key(open) { detail(open) }
                        }
                    }
                }
            } else {
                LayerPane(
                    summaries = summaries,
                    view = view,
                    onViewChange = { view = it },
                    shell = shell,
                    onLayerClick = onLayerClick,
                    onBrowseByMinistry = onBrowseByMinistry,
                    selected = null,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun LayerPane(
    summaries: List<LayerSummary>,
    view: HierarkiView,
    onViewChange: (HierarkiView) -> Unit,
    shell: PaddingValues,
    onLayerClick: (LayerSummary) -> Unit,
    onBrowseByMinistry: (LayerSummary) -> Unit,
    selected: DisplayLayer?,
    modifier: Modifier = Modifier,
) {
    val spacing = LagarTheme.spacing
    val top = shell.calculateTopPadding() + spacing.sm
    Column(modifier.fillMaxHeight()) {
        FlowRow(
            modifier = Modifier.padding(start = spacing.marginMobile, end = spacing.marginMobile, top = top),
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            HierarkiView.entries.forEach { entry ->
                PillTab(
                    text = stringResource(if (entry == HierarkiView.Layers) Res.string.hierarchy_view_layers else Res.string.hierarchy_view_pyramid),
                    selected = view == entry,
                    key = LayerKey.SfsAct,
                    onClick = { onViewChange(entry) },
                )
            }
        }
        val content = PaddingValues(
            start = spacing.marginMobile,
            end = spacing.marginMobile,
            top = spacing.sm,
            bottom = shell.calculateBottomPadding() + spacing.md,
        )
        when (view) {
            HierarkiView.Layers -> LayerOverview(summaries, content, onLayerClick, onBrowseByMinistry, selected)
            HierarkiView.Pyramid -> PyramidView(summaries, content, onLayerClick)
        }
    }
}

@Composable
private fun PyramidView(summaries: List<LayerSummary>, padding: PaddingValues, onBandClick: (LayerSummary) -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(padding),
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
    ) {
        Text(
            text = stringResource(Res.string.hierarchy_hint),
            style = LagarTheme.type.labelSm,
            color = LagarTheme.colors.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )
        NormPyramid(summaries, onBandClick)
    }
}

@Composable
private fun LayerOverview(
    summaries: List<LayerSummary>,
    padding: PaddingValues,
    onLayerClick: (LayerSummary) -> Unit,
    onBrowseByMinistry: (LayerSummary) -> Unit,
    selected: DisplayLayer?,
) {
    val spacing = LagarTheme.spacing
    val total = summaries.sumOf { it.count }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = padding,
        verticalArrangement = Arrangement.spacedBy(spacing.sm),
    ) {
        item {
            SectionHeader(
                title = stringResource(Res.string.explore_distribution_title),
                trailing = documentCount(total),
            )
        }
        item { LayerDistributionChart(summaries) }
        item { SectionHeader(title = stringResource(Res.string.explore_layers_title), modifier = Modifier.padding(top = spacing.md)) }
        items(summaries, key = { it.layer.name }) { summary ->
            LayerRow(
                summary,
                onClick = { onLayerClick(summary) },
                onBrowseByMinistry = if (summary.layer.hasMinistryIndex) ({ onBrowseByMinistry(summary) }) else null,
                selected = summary.layer == selected,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SectionHeader(title: String, modifier: Modifier = Modifier, trailing: String? = null) {
    FlowRow(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
        itemVerticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = LagarTheme.type.headlineSm, color = LagarTheme.colors.onSurface)
        if (trailing != null) {
            Text(trailing, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
        }
    }
}
