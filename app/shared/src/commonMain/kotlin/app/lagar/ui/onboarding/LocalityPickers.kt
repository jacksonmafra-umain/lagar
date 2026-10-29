package app.lagar.ui.onboarding

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.lagar.data.GeoRepository
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.Locality
import app.lagar.domain.normalize
import app.lagar.location.rememberLocationRequester
import app.lagar.resources.Res
import app.lagar.resources.ic_check
import app.lagar.resources.ic_expand_more
import app.lagar.resources.ic_info
import app.lagar.resources.ic_my_location
import app.lagar.resources.ic_search
import app.lagar.resources.location_denied
import app.lagar.resources.location_locating
import app.lagar.resources.location_outside
import app.lagar.resources.location_private
import app.lagar.resources.location_suggested
import app.lagar.resources.location_timeout
import app.lagar.resources.location_unavailable
import app.lagar.resources.location_use
import app.lagar.resources.picker_clear
import app.lagar.resources.picker_kommun_label
import app.lagar.resources.picker_kommun_needs_region
import app.lagar.resources.picker_kommun_placeholder
import app.lagar.resources.picker_no_results
import app.lagar.resources.picker_region_label
import app.lagar.resources.picker_region_placeholder
import app.lagar.resources.picker_search
import app.lagar.ui.common.GlassBottomSheet
import app.lagar.ui.common.LagarSecondaryButton
import app.lagar.ui.common.LagarTextField
import app.lagar.ui.shell.ShellDimens
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/** A named choice in a picker; [code] is what the caller stores. */
private data class Option(val code: String, val name: String)

/**
 * Searchable län and kommun selectors. The kommun field is disabled until a län is chosen, and left out when
 * [showKommun] is false; the caller decides what a new län does to the kommun (both [onRegion] and [onKommun]
 * receive null to clear).
 *
 * "Use my location" pre-selects the län and the kommun nearest to the device through the same callbacks, so the
 * caller treats it like a manual pick that the user still confirms. The position itself is not kept.
 */
@Composable
fun LocalityPickers(
    locality: Locality,
    onRegion: (String?) -> Unit,
    onKommun: (String?) -> Unit,
    modifier: Modifier = Modifier,
    showKommun: Boolean = true,
) {
    val geo = koinInject<GeoRepository>()
    // A failed load leaves the list empty (the sheet then shows "no matches") instead of crashing.
    val regions by produceState(emptyList<Option>()) {
        value = loadOptions { geo.regions().map { Option(it.code, it.name) } }
    }
    val kommuner by produceState(emptyList<Option>(), locality.regionCode) {
        value = emptyList() // drop the previous region's list at once
        val code = locality.regionCode ?: return@produceState
        value = loadOptions { geo.kommuner(code).map { Option(it.code, it.name) } }
    }
    var open by remember { mutableStateOf<Field?>(null) }
    val requester = rememberLocationRequester()
    val scope = rememberCoroutineScope()
    var suggestion by remember { mutableStateOf<LocationSuggestion>(LocationSuggestion.Idle) }

    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md)) {
        UseLocation(
            suggestion = suggestion,
            locality = locality,
            onClick = {
                scope.launch {
                    suggestion = LocationSuggestion.Locating
                    val result = suggestKommun(requester, geo::centroids)
                    suggestion = result
                    if (result is LocationSuggestion.Suggested) {
                        onRegion(result.locality.regionCode)
                        onKommun(result.locality.kommunCode)
                    }
                }
            },
        )
        PickerField(
            label = stringResource(Res.string.picker_region_label),
            value = regions.firstOrNull { it.code == locality.regionCode }?.name,
            placeholder = stringResource(Res.string.picker_region_placeholder),
            enabled = true,
            onClick = { open = Field.Region },
        )
        if (showKommun) {
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

/** The location action, its privacy note and the outcome of the last attempt (announced to screen readers). */
@Composable
private fun UseLocation(suggestion: LocationSuggestion, locality: Locality, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    val locating = suggestion == LocationSuggestion.Locating
    Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        LagarSecondaryButton(onClick = onClick, enabled = !locating, modifier = Modifier.fillMaxWidth()) {
            Icon(painterResource(Res.drawable.ic_my_location), contentDescription = null, modifier = Modifier.size(ShellDimens.SmallIconSize))
            Text(
                stringResource(if (locating) Res.string.location_locating else Res.string.location_use),
                style = LagarTheme.type.labelMd,
                modifier = Modifier.padding(start = LagarTheme.spacing.sm),
            )
        }
        val message = when (suggestion) {
            // Once the user picks something else, the suggestion no longer describes the fields.
            is LocationSuggestion.Suggested ->
                if (suggestion.locality == locality) stringResource(Res.string.location_suggested, suggestion.kommun.name) else null
            is LocationSuggestion.Failed -> stringResource(suggestion.reason.message)
            LocationSuggestion.Idle, LocationSuggestion.Locating -> null
        }
        if (message != null) {
            Row(
                modifier = Modifier.semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite },
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            ) {
                Icon(
                    painterResource(Res.drawable.ic_info),
                    contentDescription = null,
                    tint = if (suggestion is LocationSuggestion.Suggested) colors.primary else colors.onSurfaceVariant,
                    modifier = Modifier.size(ShellDimens.SmallIconSize),
                )
                Text(message, style = LagarTheme.type.bodyUi, color = colors.onSurface, modifier = Modifier.weight(1f))
            }
        }
        Text(stringResource(Res.string.location_private), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
    }
}

private val LocationSuggestion.Reason.message
    get() = when (this) {
        LocationSuggestion.Reason.Denied -> Res.string.location_denied
        LocationSuggestion.Reason.Unavailable -> Res.string.location_unavailable
        LocationSuggestion.Reason.TimedOut -> Res.string.location_timeout
        LocationSuggestion.Reason.OutsideSweden -> Res.string.location_outside
    }

private suspend fun loadOptions(load: suspend () -> List<Option>): List<Option> = try {
    load()
} catch (e: CancellationException) {
    throw e
} catch (_: Exception) {
    emptyList()
}

private enum class Field { Region, Kommun }

@Composable
private fun PickerField(label: String, value: String?, placeholder: String, enabled: Boolean, onClick: () -> Unit) {
    val colors = LagarTheme.colors
    Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
        Text(label, style = LagarTheme.type.labelMd, color = colors.onSurfaceVariant)
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = MaterialTheme.shapes.small,
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
    GlassBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        Column(
            modifier = Modifier.fillMaxHeight().navigationBarsPadding().imePadding().padding(horizontal = LagarTheme.spacing.marginMobile),
            verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = LagarTheme.type.headlineSm, color = colors.onSurface, modifier = Modifier.weight(1f))
                if (selected != null) {
                    TextButton(onClick = { onSelect(null) }) { Text(stringResource(Res.string.picker_clear)) }
                }
            }
            LagarTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = stringResource(Res.string.picker_search),
                leadingIcon = Res.drawable.ic_search,
            )
            if (shown.isEmpty()) {
                Text(
                    stringResource(Res.string.picker_no_results),
                    style = LagarTheme.type.bodyUi,
                    color = colors.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = LagarTheme.spacing.md),
                )
            }
            LazyColumn(modifier = Modifier.weight(1f).selectableGroup()) {
                items(shown, key = { it.code }) { option ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .selectable(selected = option.code == selected, role = Role.RadioButton) { onSelect(option.code) }
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
