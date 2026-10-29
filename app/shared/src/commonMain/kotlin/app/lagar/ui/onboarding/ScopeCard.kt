package app.lagar.ui.onboarding

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.Scope
import app.lagar.i18n.documentCount
import app.lagar.resources.Res
import app.lagar.resources.coming_soon
import app.lagar.resources.ic_check
import app.lagar.resources.ic_layer_apartment
import app.lagar.resources.ic_layer_balance
import app.lagar.resources.ic_layer_hospital
import app.lagar.resources.scope_active
import app.lagar.resources.scope_kommun
import app.lagar.resources.scope_kommun_desc
import app.lagar.resources.scope_national
import app.lagar.resources.scope_national_desc
import app.lagar.resources.scope_region
import app.lagar.resources.scope_region_desc
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.iconColor
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

internal fun Scope.nameRes(): StringResource = when (this) {
    Scope.Nationell -> Res.string.scope_national
    Scope.Region -> Res.string.scope_region
    Scope.Kommun -> Res.string.scope_kommun
}

internal fun Scope.descriptionRes(): StringResource = when (this) {
    Scope.Nationell -> Res.string.scope_national_desc
    Scope.Region -> Res.string.scope_region_desc
    Scope.Kommun -> Res.string.scope_kommun_desc
}

internal fun Scope.iconRes(): DrawableResource = when (this) {
    Scope.Nationell -> Res.drawable.ic_layer_balance
    Scope.Region -> Res.drawable.ic_layer_hospital
    Scope.Kommun -> Res.drawable.ic_layer_apartment
}

/** A selectable scope option: layer-colored icon, name, count badge and description. [count] null hides the badge; [active] marks the scope currently in use. */
@Composable
fun ScopeCard(
    scope: Scope,
    count: Int?,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    active: Boolean = false,
) {
    val layers = LagarTheme.layers
    val accent = layers.accent(scope.key)
    Surface(
        modifier = modifier.fillMaxWidth().selectable(selected = selected, role = Role.RadioButton, onClick = onClick),
        shape = MaterialTheme.shapes.large,
        color = layers.tint(scope.key),
        border = if (selected) BorderStroke(2.dp, accent) else BorderStroke(1.dp, layers.border(scope.key)),
    ) {
        ScopeCardContent(scope, count, active, trailing = {
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    // Unselected: an outlined ring, so the option still reads as a radio on the layer tint.
                    .background(if (selected) accent else LagarTheme.colors.surfaceContainerLowest)
                    .then(if (selected) Modifier else Modifier.border(2.dp, LagarTheme.colors.outline, CircleShape)),
                contentAlignment = Alignment.Center,
            ) {
                if (selected) {
                    Icon(painterResource(Res.drawable.ic_check), contentDescription = null, tint = accent.iconColor(), modifier = Modifier.size(18.dp))
                }
            }
        })
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ScopeCardContent(scope: Scope, count: Int?, active: Boolean, trailing: @Composable (() -> Unit)?) {
    val layers = LagarTheme.layers
    Row(
        modifier = Modifier.heightIn(min = 72.dp).padding(LagarTheme.spacing.md),
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
    ) {
        Box(
            modifier = Modifier.size(44.dp).clip(MaterialTheme.shapes.medium).background(layers.accent(scope.key)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(painterResource(scope.iconRes()), contentDescription = null, tint = layers.accent(scope.key).iconColor(), modifier = Modifier.size(24.dp))
        }
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
                verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(scope.nameRes()),
                    style = LagarTheme.type.headlineSm,
                    fontWeight = FontWeight.Bold,
                    color = layers.onTint(scope.key),
                )
                if (active) LayerBadge(scope.key, stringResource(Res.string.scope_active))
                if (count != null) {
                    LayerBadge(
                        scope.key,
                        if (count > 0) documentCount(count) else stringResource(Res.string.coming_soon),
                    )
                }
            }
            Text(
                text = stringResource(scope.descriptionRes()),
                style = LagarTheme.type.bodyUi,
                color = LagarTheme.colors.onSurfaceVariant,
            )
        }
        trailing?.invoke()
    }
}
