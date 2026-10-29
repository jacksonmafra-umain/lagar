package app.lagar.ui.onboarding

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.focus_citizen
import app.lagar.resources.focus_lawyer
import app.lagar.resources.focus_student
import app.lagar.resources.focus_text
import app.lagar.resources.focus_title
import app.lagar.resources.ic_check
import app.lagar.settings.UserFocus
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

internal fun UserFocus.labelRes(): StringResource = when (this) {
    UserFocus.Citizen -> Res.string.focus_citizen
    UserFocus.Student -> Res.string.focus_student
    UserFocus.Lawyer -> Res.string.focus_lawyer
}

/**
 * "Your main focus": a title, a line on what it changes, and one radio pill per [UserFocus]. The pills are neutral
 * (no layer colour, since a focus is not a normative layer): `primary` fill with a check when selected, glass
 * outline otherwise, each a 48dp touch target.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun FocusChoice(selected: UserFocus, onSelect: (UserFocus) -> Unit, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    Column(modifier, verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
        Text(
            stringResource(Res.string.focus_title),
            style = LagarTheme.type.labelMd,
            fontWeight = FontWeight.Bold,
            color = LagarTheme.colors.onSurface,
            modifier = Modifier.semantics { heading() },
        )
        Text(stringResource(Res.string.focus_text), style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
        FlowRow(
            modifier = Modifier.selectableGroup().padding(top = spacing.xs),
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
            verticalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            UserFocus.entries.forEach { focus ->
                FocusPill(stringResource(focus.labelRes()), selected = focus == selected, onClick = { onSelect(focus) })
            }
        }
    }
}

@Composable
private fun FocusPill(label: String, selected: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    val content = if (selected) colors.onPrimary else colors.onSurface
    Surface(
        modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).clip(CircleShape).selectable(selected = selected, role = Role.RadioButton, onClick = onClick),
        shape = CircleShape,
        color = if (selected) colors.primary else colors.surfaceContainerLowest,
        border = BorderStroke(ShellDimens.Hairline, if (selected) colors.primary else colors.outlineVariant),
    ) {
        Row(
            modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).padding(horizontal = LagarTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
        ) {
            if (selected) Icon(painterResource(Res.drawable.ic_check), contentDescription = null, tint = content, modifier = Modifier.size(ShellDimens.SmallIconSize))
            Text(label, style = LagarTheme.type.labelMd, fontWeight = FontWeight.Bold, color = content)
        }
    }
}
