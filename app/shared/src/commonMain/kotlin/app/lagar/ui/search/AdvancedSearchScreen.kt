package app.lagar.ui.search

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import app.lagar.data.GeoRepository
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.SearchMode
import app.lagar.domain.SearchQuery
import app.lagar.domain.StatusFilter
import app.lagar.resources.Res
import app.lagar.resources.advanced_clear_range
import app.lagar.resources.advanced_date_from
import app.lagar.resources.advanced_date_invalid
import app.lagar.resources.advanced_date_to
import app.lagar.resources.advanced_dates_title
import app.lagar.resources.advanced_mode_all
import app.lagar.resources.advanced_mode_fulltext
import app.lagar.resources.advanced_mode_number
import app.lagar.resources.advanced_mode_title
import app.lagar.resources.advanced_mode_title_only
import app.lagar.resources.advanced_range_invalid
import app.lagar.resources.advanced_select_all
import app.lagar.resources.advanced_status_all
import app.lagar.resources.advanced_status_repealed
import app.lagar.resources.advanced_status_title
import app.lagar.resources.advanced_text_label
import app.lagar.resources.advanced_types_title
import app.lagar.resources.coming_soon
import app.lagar.resources.home_advanced_search
import app.lagar.resources.home_scope_kommun_title
import app.lagar.resources.home_scope_region_title
import app.lagar.resources.home_search_hint
import app.lagar.resources.home_search_submit
import app.lagar.resources.meta_in_force
import app.lagar.resources.picker_clear
import app.lagar.settings.UserPreferences
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.iconColor
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.common.typeNameRes
import app.lagar.ui.onboarding.nameRes
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/** The API `type` values that filter a scope's documents, in display order; empty while a scope has no documents. */
internal fun Scope.documentTypes(): List<String> = when (this) {
    Scope.Nationell -> listOf("fundamental_law", "act", "ordinance", "other_statute")
    Scope.Region, Scope.Kommun -> emptyList()
}

/** Advanced search: the scope and locality in the header, then the filters; "Sök" opens the results. */
@Composable
fun AdvancedSearchRoute(onBack: () -> Unit, onSearch: (SearchQuery) -> Unit) {
    val preferences = koinInject<UserPreferences>()
    val geo = koinInject<GeoRepository>()
    val scope by preferences.scope.collectAsState()
    val locality by preferences.locality.collectAsState()
    val localityName by produceState<String?>(null, scope, locality) { value = localityName(geo, scope, locality) }
    AdvancedSearchScreen(scope, localityName, onBack, onSearch)
}

private suspend fun localityName(geo: GeoRepository, scope: Scope, locality: Locality): String? = when (scope) {
    Scope.Nationell -> null
    Scope.Region -> locality.regionCode?.let { code -> geo.regions().firstOrNull { it.code == code }?.name }
    Scope.Kommun -> locality.regionCode?.let { region ->
        geo.kommuner(region).firstOrNull { it.code == locality.kommunCode }?.name
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AdvancedSearchScreen(
    scope: Scope,
    localityName: String?,
    onBack: () -> Unit,
    onSearch: (SearchQuery) -> Unit,
) {
    val spacing = LagarTheme.spacing
    val layers = LagarTheme.layers
    val hazeState = remember { HazeState() }
    var headerHeight by rememberBackTopBarHeight()
    var footerPx by remember { mutableStateOf(0) }
    val density = LocalDensity.current

    var text by rememberSaveable { mutableStateOf("") }
    var fromText by rememberSaveable { mutableStateOf("") }
    var toText by rememberSaveable { mutableStateOf("") }
    var types by rememberSaveable { mutableStateOf(emptySet<String>()) }
    var mode by rememberSaveable { mutableStateOf(SearchMode.All) }
    var status by rememberSaveable { mutableStateOf(StatusFilter.All) }

    val from = parseDate(fromText)
    val to = parseDate(toText)
    val fromInvalid = fromText.isNotBlank() && from == null
    val toInvalid = toText.isNotBlank() && to == null
    val query = SearchQuery(text.trim(), types, from, to, mode, status)
    val rangeInvalid = !query.isValidRange
    val canSearch = !fromInvalid && !toInvalid && !rangeInvalid
    val invalidDate = stringResource(Res.string.advanced_date_invalid)

    Box(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .hazeSource(hazeState)
                .verticalScroll(rememberScrollState())
                .padding(
                    start = spacing.marginMobile,
                    end = spacing.marginMobile,
                    top = headerHeight + spacing.sm,
                    bottom = with(density) { footerPx.toDp() } + spacing.md,
                ),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text(stringResource(Res.string.advanced_text_label)) },
                placeholder = { Text(stringResource(Res.string.home_search_hint)) },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                shape = MaterialTheme.shapes.medium,
            )
            FilterCard(stringResource(Res.string.advanced_dates_title)) {
                DateField(
                    value = fromText,
                    onValueChange = { fromText = it },
                    label = stringResource(Res.string.advanced_date_from),
                    error = invalidDate.takeIf { fromInvalid },
                )
                DateField(
                    value = toText,
                    onValueChange = { toText = it },
                    label = stringResource(Res.string.advanced_date_to),
                    error = when {
                        toInvalid -> invalidDate
                        rangeInvalid -> stringResource(Res.string.advanced_range_invalid)
                        else -> null
                    },
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(
                        onClick = { fromText = ""; toText = "" },
                        enabled = fromText.isNotEmpty() || toText.isNotEmpty(),
                    ) { Text(stringResource(Res.string.advanced_clear_range)) }
                }
            }
            val allTypes = scope.documentTypes()
            if (allTypes.isNotEmpty()) {
                FilterCard(stringResource(Res.string.advanced_types_title)) {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing.sm), verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                        Pill(stringResource(Res.string.advanced_select_all), scope, filled = true) { types = allTypes.toSet() }
                        Pill(stringResource(Res.string.picker_clear), scope, filled = false) { types = emptySet() }
                    }
                    allTypes.forEach { type ->
                        val checked = type in types
                        val accent = layers.accent(scope.key)
                        OptionRow(
                            label = stringResource(typeNameRes(type)),
                            modifier = Modifier.toggleable(
                                value = checked,
                                role = Role.Checkbox,
                                onValueChange = { types = if (it) types + type else types - type },
                            ),
                        ) {
                            Checkbox(
                                checked = checked,
                                onCheckedChange = null,
                                colors = CheckboxDefaults.colors(checkedColor = accent, checkmarkColor = accent.iconColor()),
                            )
                        }
                    }
                }
            }
            FilterCard(stringResource(Res.string.advanced_mode_title)) {
                ModeOption(Res.string.advanced_mode_all, SearchMode.All, mode, scope) { mode = it }
                ModeOption(Res.string.advanced_mode_title_only, SearchMode.Title, mode, scope) { mode = it }
                ModeOption(Res.string.advanced_mode_number, SearchMode.Number, mode, scope) { mode = it }
                OptionRow(label = stringResource(Res.string.advanced_mode_fulltext), supporting = stringResource(Res.string.coming_soon), enabled = false) {
                    RadioButton(selected = false, onClick = null, enabled = false)
                }
            }
            FilterCard(stringResource(Res.string.advanced_status_title)) {
                StatusOption(Res.string.advanced_status_all, StatusFilter.All, status, scope) { status = it }
                StatusOption(Res.string.meta_in_force, StatusFilter.InForce, status, scope) { status = it }
                StatusOption(Res.string.advanced_status_repealed, StatusFilter.Repealed, status, scope) { status = it }
            }
        }
        Surface(
            modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth().onSizeChanged { footerPx = it.height },
            color = LagarTheme.colors.surfaceContainerLowest,
            border = BorderStroke(1.dp, LagarTheme.colors.outlineVariant),
        ) {
            val accent = layers.accent(scope.key)
            Button(
                onClick = { onSearch(query) },
                enabled = canSearch,
                modifier = Modifier
                    .windowInsetsPadding(WindowInsets.navigationBars)
                    .imePadding()
                    .padding(horizontal = spacing.marginMobile, vertical = spacing.sm)
                    .fillMaxWidth()
                    .heightIn(min = ShellDimens.TouchTarget),
                colors = ButtonDefaults.buttonColors(containerColor = accent, contentColor = accent.iconColor()),
            ) { Text(stringResource(Res.string.home_search_submit), fontWeight = FontWeight.Bold) }
        }
        BackTopBar(hazeState, onBack, { headerHeight = it }, Modifier.align(Alignment.TopCenter)) {
            Text(
                text = stringResource(Res.string.home_advanced_search),
                style = LagarTheme.type.headlineSm,
                color = LagarTheme.colors.onSurface,
                modifier = Modifier.weight(1f),
            )
            val scopeName = stringResource(scope.nameRes())
            val label = when {
                localityName == null -> scopeName
                scope == Scope.Region -> stringResource(Res.string.home_scope_region_title, localityName)
                else -> stringResource(Res.string.home_scope_kommun_title, localityName)
            }
            Text(
                text = label,
                style = LagarTheme.type.labelMd,
                fontWeight = FontWeight.Bold,
                color = layers.onTint(scope.key),
                modifier = Modifier
                    .clip(CircleShape)
                    .background(layers.tint(scope.key))
                    .padding(horizontal = spacing.sm, vertical = 6.dp),
            )
        }
    }
}

@Composable
private fun FilterCard(title: String, content: @Composable () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = LagarTheme.colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, LagarTheme.colors.outlineVariant),
    ) {
        Column(Modifier.padding(LagarTheme.spacing.md), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) {
            Text(title, style = LagarTheme.type.labelMd, fontWeight = FontWeight.Bold, color = LagarTheme.colors.onSurface)
            content()
        }
    }
}

/** A small action pill; the filled one is the primary action of its group. */
@Composable
private fun Pill(text: String, scope: Scope, filled: Boolean, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    // A 30dp pill inside a 48dp hit area.
    Box(
        modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).clip(CircleShape).clickable(role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = CircleShape,
            color = if (filled) layers.tint(scope.key) else LagarTheme.colors.surfaceContainerLowest,
            border = BorderStroke(1.dp, if (filled) layers.border(scope.key) else LagarTheme.colors.outlineVariant),
        ) {
            Text(
                text = text,
                style = LagarTheme.type.labelSm,
                fontWeight = FontWeight.Bold,
                color = if (filled) layers.onTint(scope.key) else LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.heightIn(min = 30.dp).padding(horizontal = LagarTheme.spacing.md, vertical = 6.dp),
            )
        }
    }
}

/** A 48dp-tall row: [control] then the label and optional supporting text. The caller makes it selectable or toggleable. */
@Composable
private fun OptionRow(
    label: String,
    modifier: Modifier = Modifier,
    supporting: String? = null,
    enabled: Boolean = true,
    control: @Composable () -> Unit,
) {
    Row(
        modifier = modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        control()
        Column(Modifier.weight(1f)) {
            Text(label, style = LagarTheme.type.bodyUi, color = if (enabled) LagarTheme.colors.onSurface else LagarTheme.colors.onSurfaceVariant)
            if (supporting != null) {
                Text(supporting, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun Radio(
    label: StringResource,
    selected: Boolean,
    scope: Scope,
    onSelect: () -> Unit,
) {
    OptionRow(
        label = stringResource(label),
        modifier = Modifier.selectable(selected = selected, role = Role.RadioButton, onClick = onSelect),
    ) {
        RadioButton(
            selected = selected,
            onClick = null,
            colors = RadioButtonDefaults.colors(selectedColor = LagarTheme.layers.onTint(scope.key)),
        )
    }
}

@Composable
private fun ModeOption(label: StringResource, value: SearchMode, current: SearchMode, scope: Scope, onSelect: (SearchMode) -> Unit) =
    Radio(label, value == current, scope) { onSelect(value) }

@Composable
private fun StatusOption(label: StringResource, value: StatusFilter, current: StatusFilter, scope: Scope, onSelect: (StatusFilter) -> Unit) =
    Radio(label, value == current, scope) { onSelect(value) }
