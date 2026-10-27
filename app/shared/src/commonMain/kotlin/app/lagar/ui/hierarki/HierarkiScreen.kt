package app.lagar.ui.hierarki

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.text.style.TextAlign
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.hierarchy_hint
import app.lagar.ui.common.ComingSoonSheet
import app.lagar.ui.common.LoadStateHost
import app.lagar.ui.utforska.LayerSummary
import app.lagar.ui.utforska.UtforskaViewModel
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel

/** Hierarki tab. [onOpenLayer] is called only for layers that have documents. */
@Composable
fun HierarkiRoute(onOpenLayer: (DisplayLayer) -> Unit, viewModel: UtforskaViewModel = koinViewModel()) {
    val state by viewModel.state.collectAsState()
    var comingSoon by remember { mutableStateOf<DisplayLayer?>(null) }
    HierarkiScreen(
        state = state,
        onBandClick = { if (it.count > 0) onOpenLayer(it.layer) else comingSoon = it.layer },
    )
    comingSoon?.let { ComingSoonSheet(it) { comingSoon = null } }
}

@Composable
fun HierarkiScreen(state: LoadState<List<LayerSummary>>, onBandClick: (LayerSummary) -> Unit) {
    val spacing = LagarTheme.spacing
    LoadStateHost(state) { summaries, shell ->
        Column(
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(
                PaddingValues(
                    start = spacing.marginMobile,
                    end = spacing.marginMobile,
                    top = shell.calculateTopPadding() + spacing.md,
                    bottom = shell.calculateBottomPadding() + spacing.md,
                ),
            ),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
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
}
