package app.lagar.ui.onboarding

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import app.lagar.data.GeoRepository
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.Locality
import app.lagar.domain.normalize
import app.lagar.resources.Res
import app.lagar.resources.ic_check
import app.lagar.resources.ic_expand_more
import app.lagar.resources.ic_search
import app.lagar.resources.picker_clear
import app.lagar.resources.picker_kommun_label
import app.lagar.resources.picker_kommun_needs_region
import app.lagar.resources.picker_kommun_placeholder
import app.lagar.resources.picker_no_results
import app.lagar.resources.picker_region_label
import app.lagar.resources.picker_region_placeholder
import app.lagar.resources.picker_search
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/** A named choice in a picker; [code] is what the caller stores. */
private data class Option(val code: String, val name: String)

/**
 * Searchable län and kommun selectors. The kommun field is disabled until a län is chosen; the caller
 * decides what a new län does to the kommun (both [onRegion] and [onKommun] receive null to clear).
 */
@Composable
fun LocalityPickers(
    locality: Locality,
    onRegion: (String?) -> Unit,
    onKommun: (String?) -> Unit,
    modifier: Modifier = Modifier,
) {
    val geo = koinInject<GeoRepository>()
    val regions by produceState(emptyList<Option>()) {
        value = geo.regions().map { Option(it.code, it.name) }
    }
    val kommuner by produceState(emptyList<Option>(), locality.regionCode) {
        value = locality.regionCode?.let { code -> geo.kommuner(code).map { Option(it.code, it.name) } }.orEmpty()
    }
    var open by remember { mutableStateOf<Field?>(null) }

    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md)) {
        PickerField(
            label = stringResource(Res.string.picker_region_label),
            value = regions.firstOrNull { it.code == locality.regionCode }?.name,
            placeholder = stringResource(Res.string.picker_region_placeholder),
            enabled = true,
            onClick = { open = Field.Region },
        )
        PickerField(
            label = stringResource(Res.string.picker_kommun_label),
            value = kommuner.firstOrNull { it.code == locality.kommunCode }?.name,
            placeholder = stringResource(
                if (locality.regionCode == null) Res.string.picker_kommun_needs_region else Res.string.picker_kommun_placeholder,
            ),
            enabled = locality.regionCode != null,
            onClick = { open = Field.Kommun },
        )
    }

    when (open) {
        Field.Region -> OptionSheet(
            title = stringResource(Res.string.picker_region_label),
            options = regions,
            selected = locality.regionCode,
            onSelect = { onRegion(it); open = null },
            onDismiss = { open = null },
        )
        Field.Kommun -> OptionSheet(
            title = stringResource(Res.string.picker_kommun_label),
            options = kommuner,
            selected = locality.kommunCode,
            onSelect = { onKommun(it); open = null },
            onDismiss = { open = null },
        )
        null -> Unit
    }
}

private enum class Field { Region, Kommun }

@Composable
private fun PickerField(label: String, value: String?, placeholder: String, enabled: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
        Text(label, style = LagarTheme.type.labelMd, color = colors.onSurfaceVariant)
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = MaterialTheme.shapes.medium,
            color = if (enabled) colors.surfaceContainerLowest else colors.surfaceContainerLow,
            border = BorderStroke(1.dp, colors.outlineVariant),
        ) {
            Row(
                modifier = Modifier
                    .clickable(enabled = enabled, role = Role.DropdownList, onClick = onClick)
                    .heightIn(min = ShellDimens.TouchTarget)
                    .padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            ) {
                Text(
                    text = value ?: placeholder,
                    style = LagarTheme.type.bodyUi,
                    color = when {
                        !enabled -> colors.onSurfaceVariant
                        value == null -> colors.onSurfaceVariant
                        else -> colors.onSurface
                    },
                    modifier = Modifier.weight(1f),
                )
                Icon(painterResource(Res.drawable.ic_expand_more), contentDescription = null, tint = colors.onSurfaceVariant)
            }
        }
    }
}

/** Full-height sheet with a diacritic-insensitive filter field, so 290 kommuner stay manageable. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OptionSheet(
    title: String,
    options: List<Option>,
    selected: String?,
    onSelect: (String?) -> Unit,
    onDismiss: () -> Unit,
) {
    val colors = LagarTheme.colors
    var query by remember { mutableStateOf("") }
    val shown = remember(options, query) {
        val needle = normalize(query.trim())
        if (needle.isEmpty()) options else options.filter { normalize(it.name).contains(needle) }
    }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = colors.surfaceContainerLowest,
    ) {
        Column(
            modifier = Modifier.navigationBarsPadding().padding(horizontal = LagarTheme.spacing.marginMobile),
            verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = LagarTheme.type.headlineSm, color = colors.onSurface, modifier = Modifier.weight(1f))
                if (selected != null) {
                    TextButton(onClick = { onSelect(null) }) { Text(stringResource(Res.string.picker_clear)) }
                }
            }
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text(stringResource(Res.string.picker_search)) },
                leadingIcon = { Icon(painterResource(Res.drawable.ic_search), contentDescription = null) },
                shape = MaterialTheme.shapes.medium,
            )
            if (shown.isEmpty()) {
                Text(
                    stringResource(Res.string.picker_no_results),
                    style = LagarTheme.type.bodyUi,
                    color = colors.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = LagarTheme.spacing.md),
                )
            }
            LazyColumn(modifier = Modifier.weight(1f, fill = false)) {
                items(shown, key = { it.code }) { option ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable(role = Role.Button) { onSelect(option.code) }
                            .heightIn(min = ShellDimens.TouchTarget)
                            .padding(vertical = LagarTheme.spacing.sm),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
                    ) {
                        Text(
                            option.name,
                            style = LagarTheme.type.bodyUi,
                            color = if (option.code == selected) colors.primary else colors.onSurface,
                            modifier = Modifier.weight(1f),
                        )
                        if (option.code == selected) {
                            Icon(painterResource(Res.drawable.ic_check), contentDescription = null, tint = colors.primary, modifier = Modifier.size(ShellDimens.SmallIconSize))
                        }
                    }
                }
            }
        }
    }
}
