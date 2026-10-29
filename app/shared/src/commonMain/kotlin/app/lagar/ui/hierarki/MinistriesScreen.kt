package app.lagar.ui.hierarki

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.data.ApiMinistry
import app.lagar.data.MinistryIndex
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.glass
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.document_count
import app.lagar.resources.hierarchy_by_ministry
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.ic_info
import app.lagar.resources.ministries_empty_text
import app.lagar.resources.ministries_empty_title
import app.lagar.resources.ministries_unassigned
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.iconRes
import app.lagar.ui.common.nameRes
import app.lagar.ui.common.rememberBackTopBarHeight
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/** The issuing ministries of one SFS series; [onOpenMinistry] opens that ministry's documents. */
@Composable
fun MinistriesRoute(
    layer: String,
    type: String,
    onBack: () -> Unit,
    onOpenMinistry: (ApiMinistry) -> Unit,
    viewModel: MinistriesViewModel = koinViewModel(key = "ministries/$layer/$type") { parametersOf(layer, type) },
) {
    val state by viewModel.state.collectAsState()
    MinistriesScreen(DisplayLayer.fromRoute(layer, type), state, onBack, onOpenMinistry)
}

/** Glass list of ministries with their document counts, under a back bar with the level's badge. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MinistriesScreen(
    layer: DisplayLayer?,
    state: LoadState<MinistryIndex>,
    onBack: () -> Unit,
    onOpenMinistry: (ApiMinistry) -> Unit,
) {
    val spacing = LagarTheme.spacing
    val colors = LagarTheme.colors
    val hazeState = remember { HazeState() }
    var headerHeight by rememberBackTopBarHeight()
    val bottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val key = layer?.key ?: LayerKey.SfsAct

    Box(Modifier.fillMaxSize().background(colors.surface)) {
        when (state) {
            LoadState.Loading -> Box(Modifier.fillMaxSize().padding(top = headerHeight), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            is LoadState.Failed -> Box(Modifier.fillMaxSize().padding(top = headerHeight), contentAlignment = Alignment.Center) {
                ErrorState(onRetry = state.retry)
            }
            is LoadState.Loaded -> if (state.value.ministries.isEmpty()) {
                Box(Modifier.fillMaxSize().padding(top = headerHeight, bottom = bottomInset), contentAlignment = Alignment.Center) {
                    EmptyState(
                        icon = layer?.iconRes() ?: Res.drawable.ic_info,
                        title = stringResource(Res.string.ministries_empty_title),
                        text = stringResource(Res.string.ministries_empty_text),
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                    contentPadding = PaddingValues(
                        start = spacing.marginMobile,
                        end = spacing.marginMobile,
                        top = headerHeight + spacing.md,
                        bottom = bottomInset + spacing.md,
                    ),
                    verticalArrangement = Arrangement.spacedBy(spacing.sm),
                ) {
                    items(state.value.ministries, key = { it.id }) { ministry ->
                        MinistryRow(ministry, key, onClick = { onOpenMinistry(ministry) })
                    }
                    if (state.value.unassigned > 0) {
                        item(key = "unassigned") {
                            Text(
                                pluralStringResource(Res.plurals.ministries_unassigned, state.value.unassigned, state.value.unassigned),
                                style = LagarTheme.type.labelSm,
                                color = colors.onSurfaceVariant,
                                modifier = Modifier.padding(top = spacing.xs),
                            )
                        }
                    }
                }
            }
        }
        BackTopBar(hazeState, onBack, { headerHeight = it }, Modifier.align(Alignment.TopCenter)) {
            FlowRow(
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                verticalArrangement = Arrangement.spacedBy(spacing.xs),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                if (layer != null) LayerBadge(layer, stringResource(layer.nameRes()))
                Text(stringResource(Res.string.hierarchy_by_ministry), style = LagarTheme.type.headlineSm, color = colors.onSurface)
            }
        }
    }
}

/** A tier 1 glass card with a 1dp layer border: the ministry name and its document count. */
@Composable
private fun MinistryRow(ministry: ApiMinistry, key: LayerKey, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().glass(
            GlassTier.Card,
            shape = MaterialTheme.shapes.medium,
            border = BorderStroke(1.dp, layers.border(key)),
        ),
        shape = MaterialTheme.shapes.medium,
        color = Color.Transparent,
    ) {
        Row(
            modifier = Modifier.heightIn(min = 56.dp).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(ministry.name, style = LagarTheme.type.bodyUi, fontWeight = FontWeight.Bold, color = LagarTheme.colors.onSurface)
                Text(
                    pluralStringResource(Res.plurals.document_count, ministry.count, ministry.count),
                    style = LagarTheme.type.labelSm,
                    color = layers.onTint(key),
                )
            }
            Icon(painterResource(Res.drawable.ic_chevron_right), contentDescription = null, tint = layers.onTint(key))
        }
    }
}
