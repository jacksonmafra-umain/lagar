package app.lagar.ui.onboarding

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.hasLocality
import app.lagar.resources.Res
import app.lagar.resources.onboarding_done
import app.lagar.resources.scope_step_needs_kommun
import app.lagar.resources.scope_step_needs_region
import app.lagar.resources.scope_step_text
import app.lagar.resources.scope_step_title
import org.jetbrains.compose.resources.stringResource

/**
 * Step 2: the scope the app opens on and, for Region or Kommun, the place it needs. [onDone] receives the call that
 * stores the choices (or, on skip, what can be kept of them) and runs it when it leaves.
 */
@Composable
fun ScopeStepRoute(viewModel: OnboardingViewModel, onDone: (persist: () -> Unit) -> Unit, onBack: () -> Unit) {
    val scope by viewModel.scope.collectAsState()
    val locality by viewModel.locality.collectAsState()
    val counts by viewModel.counts.collectAsState()
    ScopeStepScreen(
        selected = scope,
        locality = locality,
        counts = counts,
        onSelect = viewModel::selectScope,
        onRegion = viewModel::selectRegion,
        onKommun = viewModel::selectKommun,
        onDone = { onDone(viewModel::finish) },
        onSkip = { onDone(viewModel::skip) },
        onBack = onBack,
    )
}

/**
 * The scope cards, with the län picker (Region) or the län and kommun pickers (Kommun) opening under the selected
 * card. Done waits until the selected scope has its place, and the line above it says what is missing.
 */
@Composable
fun ScopeStepScreen(
    selected: Scope,
    locality: Locality,
    counts: Map<Scope, Int>?,
    onSelect: (Scope) -> Unit,
    onRegion: (String?) -> Unit,
    onKommun: (String?) -> Unit,
    onDone: () -> Unit,
    onSkip: () -> Unit,
    onBack: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    val missing = when {
        selected.hasLocality(locality) -> null
        selected == Scope.Region -> stringResource(Res.string.scope_step_needs_region)
        else -> stringResource(Res.string.scope_step_needs_kommun)
    }
    OnboardingScaffold(
        step = 2,
        title = stringResource(Res.string.scope_step_title),
        text = stringResource(Res.string.scope_step_text),
        primaryLabel = stringResource(Res.string.onboarding_done),
        onPrimary = onDone,
        onSkip = onSkip,
        onBack = onBack,
        primaryEnabled = missing == null,
        primaryHint = missing,
    ) {
        Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
            Scope.entries.forEach { scope ->
                ScopeCard(scope, counts?.get(scope), selected == scope, onClick = { onSelect(scope) })
                AnimatedVisibility(visible = scope == selected && scope != Scope.Nationell) {
                    LocalityPickers(
                        locality = locality,
                        onRegion = onRegion,
                        onKommun = onKommun,
                        showKommun = scope == Scope.Kommun,
                        modifier = Modifier.padding(horizontal = spacing.xs, vertical = spacing.sm),
                    )
                }
            }
        }
        StoredLocallyNote()
    }
}
