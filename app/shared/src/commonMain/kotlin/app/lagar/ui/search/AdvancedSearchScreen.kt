package app.lagar.ui.search

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import app.lagar.data.ApiIndex
import app.lagar.data.GeoRepository
import app.lagar.data.LagarRepository
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.domain.Locality
import app.lagar.domain.Scope
import app.lagar.domain.SearchMode
import app.lagar.domain.SearchQuery
import app.lagar.domain.StatusFilter
import app.lagar.resources.Res
import app.lagar.resources.advanced_clear_range
import app.lagar.resources.advanced_date_from
import app.lagar.resources.advanced_date_to
import app.lagar.resources.advanced_dates_title
import app.lagar.resources.advanced_in_force_note
import app.lagar.resources.advanced_in_force_title
import app.lagar.resources.advanced_mode_all
import app.lagar.resources.advanced_mode_fulltext
import app.lagar.resources.advanced_mode_fulltext_note
import app.lagar.resources.advanced_mode_number
import app.lagar.resources.advanced_mode_title
import app.lagar.resources.advanced_mode_title_only
import app.lagar.resources.advanced_range_invalid
import app.lagar.resources.advanced_scope_title
import app.lagar.resources.advanced_section_active
import app.lagar.resources.advanced_section_collapsed
import app.lagar.resources.advanced_section_expanded
import app.lagar.resources.advanced_select_all
import app.lagar.resources.advanced_status_all
import app.lagar.resources.advanced_status_repealed
import app.lagar.resources.advanced_status_title
import app.lagar.resources.advanced_text_label
import app.lagar.resources.advanced_types_title
import app.lagar.resources.advanced_vacatio_legis
import app.lagar.resources.drawer_change
import app.lagar.resources.home_advanced_search
import app.lagar.resources.home_scope_chip
import app.lagar.resources.home_scope_kommun_title
import app.lagar.resources.home_scope_region_title
import app.lagar.resources.home_search_hint
import app.lagar.resources.home_search_submit
import app.lagar.resources.ic_expand_more
import app.lagar.resources.ic_search
import app.lagar.resources.meta_in_force
import app.lagar.resources.picker_clear
import app.lagar.settings.UserPreferences
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.LagarButton
import app.lagar.ui.common.LagarCheckbox
import app.lagar.ui.common.LagarTextField
import app.lagar.ui.common.iconColor
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.common.typeNameRes
import app.lagar.ui.home.ScopeSheet
import app.lagar.ui.onboarding.nameRes
import app.lagar.ui.shell.LocalWideLayout
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.CancellationException
import kotlinx.datetime.LocalDate
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/**
 * The API `type` values that filter a scope's documents, in API order (layers, then their `series`): only types
 * the index lists with documents, so new types of the vocabulary appear as soon as they have data.
 */
internal fun ApiIndex.documentTypes(scope: Scope): List<String> {
    val layerIds = scope.layers.map { it.apiLayer }.distinct()
    return layers.filter { it.id in layerIds }.flatMap { layer -> layer.series.filter { it.count > 0 }.map { it.id } }
}

/** Advanced search: the scope and locality in the header, then the filters; "Sök" opens the results. */
@Composable
fun AdvancedSearchRoute(onBack: () -> Unit, onSearch: (SearchQuery) -> Unit) {
    val preferences = koinInject<UserPreferences>()
    val geo = koinInject<GeoRepository>()
    val repository = koinInject<LagarRepository>()
    val scope by preferences.scope.collectAsState()
    val locality by preferences.locality.collectAsState()
    val localityName by produceState<String?>(null, scope, locality) { value = localityName(geo, scope, locality) }
    // The type filter is decoration: without the index it is hidden, and the search still runs.
    val index by produceState<ApiIndex?>(null) {
        value = try {
            repository.index()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
    }
    var showScopeSheet by rememberSaveable { mutableStateOf(false) }
    AdvancedSearchScreen(
        scope = scope,
        localityName = localityName,
        documentTypes = index?.documentTypes(scope).orEmpty(),
        onChangeScope = { showScopeSheet = true },
        onBack = onBack,
        onSearch = onSearch,
    )
    if (showScopeSheet) ScopeSheet(onDismiss = { showScopeSheet = false })
}

/** Name of the län or kommun of a Region or Kommun [scope], or null (Nationell, or no locality chosen). */
internal suspend fun localityName(geo: GeoRepository, scope: Scope, locality: Locality): String? = when (scope) {
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
    documentTypes: List<String>,
    onChangeScope: () -> Unit,
    onBack: () -> Unit,
    onSearch: (SearchQuery) -> Unit,
) {
    val spacing = LagarTheme.spacing
    val layers = LagarTheme.layers
    val hazeState = remember { HazeState() }
    var headerHeight by rememberBackTopBarHeight()
    var footerPx by remember { mutableStateOf(0) }
    val density = LocalDensity.current
    val wide = LocalWideLayout.current

    var text by rememberSaveable { mutableStateOf("") }
    var fromIso by rememberSaveable { mutableStateOf("") }
    var toIso by rememberSaveable { mutableStateOf("") }
    var inForceFromIso by rememberSaveable { mutableStateOf("") }
    var inForceToIso by rememberSaveable { mutableStateOf("") }
    var vacatioLegis by rememberSaveable { mutableStateOf(false) }
    var types by rememberSaveable { mutableStateOf(emptySet<String>()) }
    var mode by rememberSaveable { mutableStateOf(SearchMode.All) }
    var status by rememberSaveable { mutableStateOf(StatusFilter.All) }

    // Types of another scope never filter this one.
    val activeTypes = types intersect documentTypes.toSet()
    val query = SearchQuery(
        text = text.trim(),
        types = activeTypes,
        from = parseDate(fromIso),
        to = parseDate(toIso),
        mode = mode,
        status = status,
        inForceFrom = parseDate(inForceFromIso),
        inForceTo = parseDate(inForceToIso),
        vacatioLegis = vacatioLegis,
    )
    val issuedInvalid = query.from != null && query.to != null && query.from > query.to
    val inForceInvalid = query.inForceFrom != null && query.inForceTo != null && query.inForceFrom > query.inForceTo
    val rangeError = stringResource(Res.string.advanced_range_invalid)

    // On desktop the filters form two columns within the form width, and the search button sits under the right one.
    BoxWithConstraints(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
        val side = if (wide) maxOf(spacing.margin, (maxWidth - ShellDimens.FormMaxWidth) / 2) else spacing.marginMobile
        val textScopeModeTypes: @Composable ColumnScope.() -> Unit = {
            LagarTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.fillMaxWidth(),
                label = stringResource(Res.string.advanced_text_label),
                placeholder = stringResource(Res.string.home_search_hint),
                leadingIcon = Res.drawable.ic_search,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
            )
            ScopeCard(scope, localityName, onChangeScope)
            FilterCard(stringResource(Res.string.advanced_mode_title), scope, active = mode != SearchMode.All) {
                ModeOption(Res.string.advanced_mode_all, SearchMode.All, mode, scope) { mode = it }
                ModeOption(Res.string.advanced_mode_title_only, SearchMode.Title, mode, scope) { mode = it }
                ModeOption(Res.string.advanced_mode_number, SearchMode.Number, mode, scope) { mode = it }
                ModeOption(Res.string.advanced_mode_fulltext, SearchMode.FullText, mode, scope, Res.string.advanced_mode_fulltext_note) { mode = it }
            }
            if (documentTypes.isNotEmpty()) {
                FilterCard(stringResource(Res.string.advanced_types_title), scope, active = activeTypes.isNotEmpty()) {
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing.sm), verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                        Pill(stringResource(Res.string.advanced_select_all), scope, filled = true) { types = documentTypes.toSet() }
                        Pill(stringResource(Res.string.picker_clear), scope, filled = false) { types = emptySet() }
                    }
                    documentTypes.forEach { type ->
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
                            LagarCheckbox(checked = checked, onCheckedChange = null, color = accent)
                        }
                    }
                }
            }
        }
        val datesAndStatus: @Composable ColumnScope.() -> Unit = {
            FilterCard(
                stringResource(Res.string.advanced_dates_title),
                scope,
                active = fromIso.isNotEmpty() || toIso.isNotEmpty(),
                initiallyExpanded = false,
            ) {
                DateRange(
                    from = query.from,
                    to = query.to,
                    onFrom = { fromIso = it.toString() },
                    onTo = { toIso = it.toString() },
                    onClear = { fromIso = ""; toIso = "" },
                    error = rangeError.takeIf { issuedInvalid },
                    scope = scope,
                )
            }
            FilterCard(
                stringResource(Res.string.advanced_in_force_title),
                scope,
                active = inForceFromIso.isNotEmpty() || inForceToIso.isNotEmpty() || vacatioLegis,
                initiallyExpanded = false,
            ) {
                Text(stringResource(Res.string.advanced_in_force_note), style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
                DateRange(
                    from = query.inForceFrom,
                    to = query.inForceTo,
                    onFrom = { inForceFromIso = it.toString() },
                    onTo = { inForceToIso = it.toString() },
                    onClear = { inForceFromIso = ""; inForceToIso = "" },
                    error = rangeError.takeIf { inForceInvalid },
                    scope = scope,
                )
                OptionRow(
                    label = stringResource(Res.string.advanced_vacatio_legis),
                    modifier = Modifier.toggleable(value = vacatioLegis, role = Role.Checkbox, onValueChange = { vacatioLegis = it }),
                ) {
                    LagarCheckbox(checked = vacatioLegis, onCheckedChange = null, color = layers.accent(scope.key))
                }
            }
            FilterCard(stringResource(Res.string.advanced_status_title), scope, active = status != StatusFilter.All, initiallyExpanded = false) {
                StatusOption(Res.string.advanced_status_all, StatusFilter.All, status, scope) { status = it }
                StatusOption(Res.string.meta_in_force, StatusFilter.InForce, status, scope) { status = it }
                StatusOption(Res.string.advanced_status_repealed, StatusFilter.Repealed, status, scope) { status = it }
            }
        }
        Column(
            modifier = Modifier
                .fillMaxSize()
                .hazeSource(hazeState)
                .verticalScroll(rememberScrollState())
                .padding(
                    start = side,
                    end = side,
                    top = headerHeight + spacing.sm,
                    bottom = with(density) { footerPx.toDp() } + spacing.md,
                ),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            if (wide) {
                Row(horizontalArrangement = Arrangement.spacedBy(spacing.gutter)) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(spacing.md), content = textScopeModeTypes)
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(spacing.md), content = datesAndStatus)
                }
            } else {
                textScopeModeTypes()
                datesAndStatus()
            }
        }
        // Sticky footer: a tier 2 glass bar over the scrolling form.
        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .onSizeChanged { footerPx = it.height }
                .glass(GlassTier.Bar, hazeState),
        ) {
            val accent = layers.accent(scope.key)
            LagarButton(
                onClick = { onSearch(query) },
                enabled = query.isValidRange,
                modifier = Modifier
                    .windowInsetsPadding(WindowInsets.navigationBars)
                    .imePadding()
                    .padding(horizontal = side, vertical = spacing.sm)
                    .then(if (wide) Modifier.fillMaxWidth().wrapContentWidth(Alignment.End).widthIn(min = WideSubmitMinWidth) else Modifier.fillMaxWidth()),
                containerColor = accent,
                contentColor = accent.iconColor(),
            ) { Text(stringResource(Res.string.home_search_submit), fontWeight = FontWeight.Bold) }
        }
        BackTopBar(hazeState, onBack, { headerHeight = it }, Modifier.align(Alignment.TopCenter)) {
            Text(
                text = stringResource(Res.string.home_advanced_search),
                style = LagarTheme.type.headlineSm,
                color = LagarTheme.colors.onSurface,
                modifier = Modifier.weight(1f),
            )
            val label = scopeLabel(scope, localityName)
            val chipDescription = stringResource(Res.string.home_scope_chip, label)
            Box(
                modifier = Modifier
                    .heightIn(min = ShellDimens.TouchTarget)
                    .clip(CircleShape)
                    .clickable(role = Role.Button, onClick = onChangeScope)
                    .semantics(mergeDescendants = true) { contentDescription = chipDescription },
                contentAlignment = Alignment.Center,
            ) {
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
}

/** "Nationell", "Region: Skåne län" or "Kommun: Lund"; the bare scope name while the locality is unknown. */
@Composable
internal fun scopeLabel(scope: Scope, localityName: String?): String {
    val scopeName = stringResource(scope.nameRes())
    return when {
        localityName == null -> scopeName
        scope == Scope.Region -> stringResource(Res.string.home_scope_region_title, localityName)
        else -> stringResource(Res.string.home_scope_kommun_title, localityName)
    }
}

/** The scope searched, with a "Change" pill that opens the scope sheet. */
@Composable
private fun ScopeCard(scope: Scope, localityName: String?, onChange: () -> Unit) {
    val layers = LagarTheme.layers
    Surface(
        modifier = Modifier.fillMaxWidth().glass(GlassTier.Card, shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, layers.border(scope.key))),
        shape = MaterialTheme.shapes.large,
        color = Color.Transparent,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Column(Modifier.weight(1f)) {
                Text(stringResource(Res.string.advanced_scope_title), style = LagarTheme.type.labelSm, color = layers.onTint(scope.key))
                Text(scopeLabel(scope, localityName), style = LagarTheme.type.bodyUi, fontWeight = FontWeight.Bold, color = LagarTheme.colors.onSurface)
            }
            Pill(stringResource(Res.string.drawer_change), scope, filled = true, onClick = onChange)
        }
    }
}

/** From and to [DateField]s, the range [error] under "to", and a "Clear range" button. */
@Composable
private fun DateRange(
    from: LocalDate?,
    to: LocalDate?,
    onFrom: (LocalDate) -> Unit,
    onTo: (LocalDate) -> Unit,
    onClear: () -> Unit,
    error: String?,
    scope: Scope,
) {
    DateField(from, onFrom, stringResource(Res.string.advanced_date_from), error = null, layerKey = scope.key)
    DateField(to, onTo, stringResource(Res.string.advanced_date_to), error = error, layerKey = scope.key)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        TextButton(onClick = onClear, enabled = from != null || to != null) {
            Text(stringResource(Res.string.advanced_clear_range), color = LagarTheme.layers.onTint(scope.key))
        }
    }
}

/**
 * A collapsible filter section: the header row (48dp, `Role.Button`, expanded state announced) shows the title,
 * an "Active" badge while the section holds a non-default value, and a chevron that turns when open.
 */
private val WideSubmitMinWidth = 240.dp

@Composable
private fun FilterCard(
    title: String,
    scope: Scope,
    active: Boolean,
    initiallyExpanded: Boolean = true,
    content: @Composable () -> Unit,
) {
    var expanded by rememberSaveable(title) { mutableStateOf(initiallyExpanded) }
    val layers = LagarTheme.layers
    val stateText = stringResource(if (expanded) Res.string.advanced_section_expanded else Res.string.advanced_section_collapsed)
    val rotation by animateFloatAsState(if (expanded) 180f else 0f)
    Surface(
        modifier = Modifier.fillMaxWidth().glass(GlassTier.Card, shape = MaterialTheme.shapes.large),
        shape = MaterialTheme.shapes.large,
        color = Color.Transparent,
    ) {
        Column(Modifier.padding(horizontal = LagarTheme.spacing.md).padding(bottom = if (expanded) LagarTheme.spacing.md else 0.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = ShellDimens.TouchTarget)
                    .clickable(role = Role.Button) { expanded = !expanded }
                    .semantics(mergeDescendants = true) { stateDescription = stateText },
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            ) {
                Text(
                    title,
                    style = LagarTheme.type.labelMd,
                    fontWeight = FontWeight.Bold,
                    color = LagarTheme.colors.onSurface,
                    modifier = Modifier.weight(1f).semantics { heading() },
                )
                if (active) {
                    Text(
                        stringResource(Res.string.advanced_section_active),
                        style = LagarTheme.type.labelSm,
                        fontWeight = FontWeight.Bold,
                        color = layers.onTint(scope.key),
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(layers.tint(scope.key))
                            .padding(horizontal = LagarTheme.spacing.sm, vertical = 2.dp),
                    )
                }
                Icon(
                    painterResource(Res.drawable.ic_expand_more),
                    contentDescription = null,
                    tint = LagarTheme.colors.onSurfaceVariant,
                    modifier = Modifier.size(ShellDimens.SmallIconSize).rotate(rotation),
                )
            }
            AnimatedVisibility(visible = expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs)) { content() }
            }
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
    control: @Composable () -> Unit,
) {
    Row(
        modifier = modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        control()
        Column(Modifier.weight(1f)) {
            Text(label, style = LagarTheme.type.bodyUi, color = LagarTheme.colors.onSurface)
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
    supporting: StringResource? = null,
    onSelect: () -> Unit,
) {
    OptionRow(
        label = stringResource(label),
        supporting = supporting?.let { stringResource(it) },
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
private fun ModeOption(
    label: StringResource,
    value: SearchMode,
    current: SearchMode,
    scope: Scope,
    supporting: StringResource? = null,
    onSelect: (SearchMode) -> Unit,
) = Radio(label, value == current, scope, supporting) { onSelect(value) }

@Composable
private fun StatusOption(label: StringResource, value: StatusFilter, current: StatusFilter, scope: Scope, onSelect: (StatusFilter) -> Unit) =
    Radio(label, value == current, scope) { onSelect(value) }
