package app.lagar.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.Locality
import app.lagar.resources.Res
import app.lagar.resources.locality_step_text
import app.lagar.resources.locality_step_title
import app.lagar.resources.onboarding_done
import app.lagar.resources.onboarding_stored_locally
import org.jetbrains.compose.resources.stringResource

/** Step 3: pick region and kommun, both optional. [onDone] runs after the choices are stored. */
@Composable
fun LocalityStepRoute(viewModel: OnboardingViewModel, onDone: () -> Unit) {
    val locality by viewModel.locality.collectAsState()
    LocalityStepScreen(
        locality = locality,
        onRegion = viewModel::selectRegion,
        onKommun = viewModel::selectKommun,
        onDone = {
            viewModel.finish()
            onDone()
        },
    )
}

@Composable
fun LocalityStepScreen(locality: Locality, onRegion: (String?) -> Unit, onKommun: (String?) -> Unit, onDone: () -> Unit) {
    OnboardingScaffold(
        step = 3,
        title = stringResource(Res.string.locality_step_title),
        text = stringResource(Res.string.locality_step_text),
        primaryLabel = stringResource(Res.string.onboarding_done),
        onPrimary = onDone,
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md)) {
            LocalityPickers(locality, onRegion, onKommun)
            Text(
                stringResource(Res.string.onboarding_stored_locally),
                style = LagarTheme.type.labelSm,
                color = LagarTheme.colors.onSurfaceVariant,
            )
        }
    }
}
