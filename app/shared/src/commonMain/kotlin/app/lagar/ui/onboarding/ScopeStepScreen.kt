package app.lagar.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.onboarding_continue
import app.lagar.resources.scope_step_text
import app.lagar.resources.scope_step_title
import org.jetbrains.compose.resources.stringResource

/** Step 2: pick the scope the app opens on. */
@Composable
fun ScopeStepRoute(viewModel: OnboardingViewModel, onContinue: () -> Unit, onSkip: () -> Unit) {
    val scope by viewModel.scope.collectAsState()
    val counts by viewModel.counts.collectAsState()
    ScopeStepScreen(scope, counts, viewModel::selectScope, onContinue, onSkip)
}

@Composable
fun ScopeStepScreen(
    selected: Scope,
    counts: Map<Scope, Int>?,
    onSelect: (Scope) -> Unit,
    onContinue: () -> Unit,
    onSkip: () -> Unit,
) {
    OnboardingScaffold(
        step = 2,
        title = stringResource(Res.string.scope_step_title),
        text = stringResource(Res.string.scope_step_text),
        primaryLabel = stringResource(Res.string.onboarding_continue),
        onPrimary = onContinue,
        onSkip = onSkip,
    ) {
        Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
            Scope.entries.forEach { scope ->
                ScopeCard(scope, counts?.get(scope), selected == scope, onClick = { onSelect(scope) })
            }
        }
    }
}
