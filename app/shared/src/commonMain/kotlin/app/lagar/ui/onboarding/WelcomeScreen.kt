package app.lagar.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.ic_layer_crown
import app.lagar.resources.onboarding_continue
import app.lagar.resources.welcome_text
import app.lagar.resources.welcome_title
import app.lagar.settings.UserFocus
import app.lagar.ui.shell.LocalWideLayout
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Step 1: what the app covers, and the user's main focus. */
@Composable
fun WelcomeRoute(viewModel: OnboardingViewModel, onContinue: () -> Unit, onSkip: () -> Unit) {
    val focus by viewModel.focus.collectAsState()
    WelcomeScreen(focus, viewModel::selectFocus, onContinue, onSkip)
}

/**
 * The focus choice is the step's only decision, so it follows the introduction directly; the scopes are chosen
 * on the next step. The Lagar card fills the desktop side column only: on a phone it would push the choice down.
 */
@Composable
fun WelcomeScreen(
    focus: UserFocus,
    onFocus: (UserFocus) -> Unit,
    onContinue: () -> Unit,
    onSkip: () -> Unit,
) {
    OnboardingScaffold(
        step = 1,
        title = stringResource(Res.string.welcome_title),
        text = stringResource(Res.string.welcome_text),
        primaryLabel = stringResource(Res.string.onboarding_continue),
        onPrimary = onContinue,
        onSkip = onSkip,
        aside = if (LocalWideLayout.current) ({ Hero() }) else null,
    ) {
        FocusChoice(focus, onFocus)
    }
}

@Composable
private fun Hero() {
    val colors = LagarTheme.colors
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(144.dp)
            .clip(MaterialTheme.shapes.extraLarge)
            .background(colors.primary),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
            Icon(painterResource(Res.drawable.ic_layer_crown), contentDescription = null, tint = colors.onPrimary, modifier = Modifier.size(48.dp))
            Text(stringResource(Res.string.app_name), style = LagarTheme.type.headlineMd, color = colors.onPrimary)
        }
    }
}
