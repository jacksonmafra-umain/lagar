package app.lagar.ui.utforska

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.document_count
import app.lagar.resources.explore_distribution_title
import app.lagar.resources.explore_layers_title
import app.lagar.ui.common.ComingSoonSheet
import app.lagar.ui.common.LoadStateHost
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel

/** Utforska tab. [onOpenLayer] is called only for layers that have documents. */
@Composable
fun UtforskaRoute(onOpenLayer: (DisplayLayer) -> Unit, viewModel: UtforskaViewModel = koinViewModel()) {
    val state by viewModel.state.collectAsState()
    var comingSoon by remember { mutableStateOf<DisplayLayer?>(null) }
    UtforskaScreen(
        state = state,
        onLayerClick = { if (it.count > 0) onOpenLayer(it.layer) else comingSoon = it.layer },
    )
    comingSoon?.let { ComingSoonSheet(it) { comingSoon = null } }
}

@Composable
fun UtforskaScreen(state: LoadState<List<LayerSummary>>, onLayerClick: (LayerSummary) -> Unit) {
    LoadStateHost(state) { summaries, shell -> LayerOverview(summaries, shell, onLayerClick) }
}

@Composable
private fun LayerOverview(summaries: List<LayerSummary>, shell: PaddingValues, onLayerClick: (LayerSummary) -> Unit) {
    val spacing = LagarTheme.spacing
    val total = summaries.sumOf { it.count }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = spacing.marginMobile,
            end = spacing.marginMobile,
            top = shell.calculateTopPadding() + spacing.md,
            bottom = shell.calculateBottomPadding() + spacing.md,
        ),
        verticalArrangement = Arrangement.spacedBy(spacing.sm),
    ) {
        item {
            SectionHeader(
                title = stringResource(Res.string.explore_distribution_title),
                trailing = pluralStringResource(Res.plurals.document_count, total, total),
            )
        }
        item { LayerDistributionChart(summaries) }
        item { SectionHeader(title = stringResource(Res.string.explore_layers_title), modifier = Modifier.padding(top = spacing.md)) }
        items(summaries, key = { it.layer.name }) { LayerRow(it, onClick = { onLayerClick(it) }) }
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
