package app.lagar.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.ic_arrow_back
import app.lagar.resources.ic_arrow_forward
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.onboarding_back
import app.lagar.resources.onboarding_skip
import app.lagar.resources.onboarding_step
import app.lagar.resources.onboarding_stored_locally
import app.lagar.ui.common.LagarButton
import app.lagar.ui.common.LagarSecondaryButton
import app.lagar.ui.shell.LocalWideLayout
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

internal const val ONBOARDING_STEPS = 3

/** "Step N of 3" pill with a three-segment progress bar; the bar is decoration, the pill carries the meaning. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun StepHeader(step: Int, modifier: Modifier = Modifier) {
    val colors = LagarTheme.colors
    FlowRow(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
        itemVerticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(shape = CircleShape, color = colors.surfaceContainerHigh) {
            Text(
                text = stringResource(Res.string.onboarding_step, step, ONBOARDING_STEPS),
                style = LagarTheme.type.labelMd,
                color = colors.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.xs),
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
            repeat(ONBOARDING_STEPS) { i ->
                Row(
                    Modifier
                        .width(if (i + 1 == step) 32.dp else 16.dp)
                        .height(4.dp)
                        .clip(CircleShape)
                        .background(if (i + 1 <= step) colors.primary else colors.outlineVariant),
                ) {}
            }
        }
    }
}

/**
 * Shared frame of the three steps: a fixed top row with the step header and Skip at the top right (as in the
 * Stitch steps), title and text on a scrolling body, and the primary action fixed at the bottom. Skip leaves
 * onboarding with the defaults from any step. With [onBack] (steps 2 and 3) the top row starts with a back arrow
 * that returns to the previous step. Fills the screen, inside the system bars. [aside] (the welcome
 * illustration) follows the text on phones; on desktop the title, text and [aside] form a left column beside
 * the choices, and the frame is capped at [ShellDimens.FormMaxWidth].
 */
@Composable
internal fun OnboardingScaffold(
    step: Int,
    title: String,
    text: String,
    primaryLabel: String,
    onPrimary: () -> Unit,
    onSkip: () -> Unit,
    modifier: Modifier = Modifier,
    onBack: (() -> Unit)? = null,
    aside: (@Composable ColumnScope.() -> Unit)? = null,
    body: @Composable ColumnScope.() -> Unit,
) {
    val frame = modifier.fillMaxSize().background(LagarTheme.colors.surface).windowInsetsPadding(WindowInsets.systemBars)
    if (LocalWideLayout.current) {
        WideOnboardingScaffold(step, title, text, primaryLabel, onPrimary, onSkip, onBack, frame, aside, body)
        return
    }
    val spacing = LagarTheme.spacing
    Column(modifier = frame) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(start = spacing.marginMobile, end = spacing.marginMobile, top = spacing.sm),
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            onBack?.let { BackButton(it) }
            StepHeader(step, Modifier.weight(1f))
            SkipButton(onSkip)
        }
        Column(
            modifier = Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = spacing.marginMobile, vertical = spacing.md),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            Text(title, style = LagarTheme.type.headlineLgMobile, color = LagarTheme.colors.onSurface, modifier = Modifier.semantics { heading() })
            Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurfaceVariant)
            aside?.invoke(this)
            body()
        }
        LagarButton(
            onClick = onPrimary,
            modifier = Modifier.fillMaxWidth().padding(horizontal = spacing.marginMobile, vertical = spacing.md),
        ) {
            PrimaryLabel(primaryLabel)
        }
    }
}

/** Desktop frame: the step row on top, then the title column (2/5) beside the scrolling choices (3/5), which end with the primary action. */
@Composable
private fun WideOnboardingScaffold(
    step: Int,
    title: String,
    text: String,
    primaryLabel: String,
    onPrimary: () -> Unit,
    onSkip: () -> Unit,
    onBack: (() -> Unit)?,
    modifier: Modifier,
    aside: (@Composable ColumnScope.() -> Unit)?,
    body: @Composable ColumnScope.() -> Unit,
) {
    val spacing = LagarTheme.spacing
    Box(modifier, contentAlignment = Alignment.TopCenter) {
        Column(Modifier.fillMaxHeight().widthIn(max = ShellDimens.FormMaxWidth).fillMaxWidth().padding(horizontal = spacing.margin)) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = spacing.md),
                horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                onBack?.let { BackButton(it) }
                StepHeader(step, Modifier.weight(1f))
                SkipButton(onSkip)
            }
            Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(spacing.xl)) {
                Column(
                    modifier = Modifier.weight(2f).fillMaxHeight().verticalScroll(rememberScrollState()).padding(vertical = spacing.lg),
                    verticalArrangement = Arrangement.spacedBy(spacing.md),
                ) {
                    Text(title, style = LagarTheme.type.headlineLg, color = LagarTheme.colors.onSurface, modifier = Modifier.semantics { heading() })
                    Text(text, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurfaceVariant)
                    aside?.invoke(this)
                }
                Column(
                    modifier = Modifier.weight(3f).fillMaxHeight().verticalScroll(rememberScrollState()).padding(vertical = spacing.lg),
                    verticalArrangement = Arrangement.spacedBy(spacing.md),
                ) {
                    body()
                    LagarButton(
                        onClick = onPrimary,
                        modifier = Modifier.align(Alignment.End).widthIn(min = WidePrimaryMinWidth).padding(top = spacing.sm),
                    ) {
                        PrimaryLabel(primaryLabel)
                    }
                }
            }
        }
    }
}

@Composable
private fun PrimaryLabel(label: String) {
    Text(label)
    Spacer(Modifier.width(LagarTheme.spacing.sm))
    Icon(painterResource(Res.drawable.ic_arrow_forward), contentDescription = null, modifier = Modifier.size(ShellDimens.SmallIconSize))
}

private val WidePrimaryMinWidth = 240.dp

/** The Stitch back arrow at the top left of steps 2 and 3: a 48dp round target, labelled for screen readers. */
@Composable
private fun BackButton(onClick: () -> Unit) {
    val description = stringResource(Res.string.onboarding_back)
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(painterResource(Res.drawable.ic_arrow_back), contentDescription = null, tint = LagarTheme.colors.onSurfaceVariant)
    }
}

/** The Stitch "Skip ›" pill: a glass secondary button. */
@Composable
private fun SkipButton(onClick: () -> Unit) {
    LagarSecondaryButton(onClick = onClick) {
        Text(stringResource(Res.string.onboarding_skip), style = LagarTheme.type.labelMd)
        Spacer(Modifier.width(LagarTheme.spacing.xs))
        Icon(painterResource(Res.drawable.ic_chevron_right), contentDescription = null, modifier = Modifier.size(ShellDimens.SmallIconSize))
    }
}

/** "Stored on this device only", under the choices of steps 2 and 3. */
@Composable
internal fun StoredLocallyNote(modifier: Modifier = Modifier) {
    Text(
        stringResource(Res.string.onboarding_stored_locally),
        style = LagarTheme.type.labelSm,
        color = LagarTheme.colors.onSurfaceVariant,
        modifier = modifier,
    )
}
