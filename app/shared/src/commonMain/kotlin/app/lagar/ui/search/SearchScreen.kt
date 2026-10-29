package app.lagar.ui.search

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import app.lagar.domain.SearchHit
import app.lagar.domain.SearchQuery
import app.lagar.domain.SortOrder
import app.lagar.domain.highlightRanges
import app.lagar.resources.Res
import app.lagar.resources.coming_soon
import app.lagar.resources.home_advanced_search
import app.lagar.resources.home_coming_soon_text
import app.lagar.resources.home_search_hint
import app.lagar.resources.ic_info
import app.lagar.resources.ic_search
import app.lagar.resources.search_match_body
import app.lagar.resources.search_no_results_text
import app.lagar.resources.search_no_results_title
import app.lagar.resources.search_prompt_text
import app.lagar.resources.search_prompt_title
import app.lagar.resources.search_result_count
import app.lagar.resources.search_sort_label
import app.lagar.resources.search_sort_newest
import app.lagar.resources.search_sort_number
import app.lagar.resources.search_sort_relevance
import app.lagar.settings.UserPreferences
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.InputFrame
import app.lagar.ui.common.PillTab
import app.lagar.ui.common.ShortcutHint
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.common.searchShortcutHint
import app.lagar.ui.home.displayLayer
import app.lagar.ui.list.STATUTE_COLUMNS
import app.lagar.ui.list.StatuteRow
import app.lagar.ui.list.StatuteRowPair
import app.lagar.ui.navigation.Search
import app.lagar.ui.shell.LocalWideLayout
import app.lagar.ui.shell.ShellDimens
import app.lagar.ui.shell.wideListPadding
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/** Search results for the query carried by [route]; typing in the top bar refines it. */
@Composable
fun SearchRoute(
    route: Search,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    onOpenAdvancedSearch: () -> Unit,
    focusRequests: Int = 0,
    viewModel: SearchViewModel = koinViewModel(key = route.toString()) { parametersOf(route.toQuery()) },
) {
    val query by viewModel.query.collectAsState()
    val results by viewModel.results.collectAsState()
    val scope by koinInject<UserPreferences>().scope.collectAsState()
    SearchScreen(
        query = query,
        results = results,
        scope = scope,
        onQueryChange = viewModel::update,
        onBack = onBack,
        onOpenDocument = onOpenDocument,
        onOpenAdvancedSearch = onOpenAdvancedSearch,
        focusRequests = focusRequests,
    )
}

/** [focusRequests] moves focus to the search field each time it grows (the web search shortcut). */
@Composable
fun SearchScreen(
    query: SearchQuery,
    results: LoadState<List<SearchHit>>,
    scope: Scope,
    onQueryChange: (SearchQuery) -> Unit,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    onOpenAdvancedSearch: () -> Unit,
    focusRequests: Int = 0,
) {
    val spacing = LagarTheme.spacing
    val hazeState = remember { HazeState() }
    var headerHeight by rememberBackTopBarHeight()
    val bottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    val centered = Modifier.fillMaxSize().padding(top = headerHeight)
    val wide = LocalWideLayout.current

    // On desktop the results fill two columns within the content width.
    BoxWithConstraints(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
        val side = if (wide) wideListPadding(maxWidth, spacing.margin) else spacing.marginMobile
        // Only the national level has documents so far, so other scopes never reach the results.
        val state = if (scope == Scope.Nationell) results else LoadState.Loaded(emptyList())
        when (state) {
            LoadState.Loading -> Box(centered, contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            is LoadState.Failed -> Box(centered, contentAlignment = Alignment.Center) { ErrorState(onRetry = state.retry) }
            is LoadState.Loaded -> LazyColumn(
                modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                contentPadding = PaddingValues(
                    start = side,
                    end = side,
                    top = headerHeight + spacing.xs,
                    bottom = bottomInset + spacing.md,
                ),
                verticalArrangement = Arrangement.spacedBy(spacing.sm),
            ) {
                val showCount = scope == Scope.Nationell && query.isActive && state.value.isNotEmpty()
                item(key = "summary") {
                    SummaryRow(count = state.value.size.takeIf { showCount }, scope = scope, onOpenAdvancedSearch = onOpenAdvancedSearch)
                }
                when {
                    scope != Scope.Nationell -> item(key = "state") {
                        EmptyState(Res.drawable.ic_info, stringResource(Res.string.coming_soon), stringResource(Res.string.home_coming_soon_text))
                    }
                    !query.isActive -> item(key = "state") {
                        EmptyState(Res.drawable.ic_search, stringResource(Res.string.search_prompt_title), stringResource(Res.string.search_prompt_text))
                    }
                    state.value.isEmpty() -> item(key = "state") {
                        EmptyState(Res.drawable.ic_search, stringResource(Res.string.search_no_results_title), stringResource(Res.string.search_no_results_text))
                    }
                    else -> {
                        item(key = "sort") {
                            SortRow(query.sort, scope) { onQueryChange(query.copy(sort = it)) }
                        }
                        // On desktop the results fill two columns.
                        if (wide) {
                            items(state.value.chunked(STATUTE_COLUMNS), key = { it.first().item.id }) { pair ->
                                StatuteRowPair(pair) { hit, modifier -> SearchHitRow(hit, query.text, onOpenDocument, modifier) }
                            }
                        } else {
                            items(state.value, key = { it.item.id }) { hit -> SearchHitRow(hit, query.text, onOpenDocument) }
                        }
                    }
                }
            }
        }
        BackTopBar(hazeState, onBack, { headerHeight = it }, Modifier.align(Alignment.TopCenter)) {
            SearchInput(
                initial = query.text,
                autoFocus = !query.isActive,
                focusRequests = focusRequests,
                scope = scope,
                onChange = { onQueryChange(query.copy(text = it)) },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

/** One result: the title matches highlighted, and a note when only the body matched. */
@Composable
private fun SearchHitRow(hit: SearchHit, text: String, onOpenDocument: (String) -> Unit, modifier: Modifier = Modifier) {
    val item = hit.item
    StatuteRow(
        item = item,
        layer = item.displayLayer() ?: DisplayLayer.SfsAct,
        onClick = { onOpenDocument(item.id) },
        modifier = modifier,
        highlights = highlightRanges(item.title, text),
        note = if (hit.bodyOnly) stringResource(Res.string.search_match_body) else null,
    )
}

/** Result count on the left, the advanced-search link on the right; wraps at large font sizes. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SummaryRow(count: Int?, scope: Scope, onOpenAdvancedSearch: () -> Unit) {
    val layers = LagarTheme.layers
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        itemVerticalAlignment = Alignment.CenterVertically,
    ) {
        if (count != null) {
            Text(
                text = pluralStringResource(Res.plurals.search_result_count, count, count),
                style = LagarTheme.type.labelMd,
                color = LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.padding(end = LagarTheme.spacing.sm),
            )
        } else {
            Box(Modifier)
        }
        Row(
            modifier = Modifier
                .heightIn(min = ShellDimens.TouchTarget)
                .clip(MaterialTheme.shapes.small)
                .clickable(role = Role.Button, onClick = onOpenAdvancedSearch)
                .padding(horizontal = LagarTheme.spacing.xs),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
        ) {
            Icon(painterResource(Res.drawable.ic_search), null, tint = layers.onTint(scope.key), modifier = Modifier.size(16.dp))
            Text(
                text = stringResource(Res.string.home_advanced_search),
                style = LagarTheme.type.labelSm,
                fontWeight = FontWeight.Bold,
                color = layers.onTint(scope.key),
            )
        }
    }
}

/** The result order: relevance, newest first or by number. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SortRow(current: SortOrder, scope: Scope, onSelect: (SortOrder) -> Unit) {
    FlowRow(
        modifier = Modifier.fillMaxWidth().selectableGroup(),
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        itemVerticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = stringResource(Res.string.search_sort_label),
            style = LagarTheme.type.labelMd,
            color = LagarTheme.colors.onSurfaceVariant,
        )
        SortOrder.entries.forEach { order ->
            val label = when (order) {
                SortOrder.Relevance -> Res.string.search_sort_relevance
                SortOrder.Newest -> Res.string.search_sort_newest
                SortOrder.Number -> Res.string.search_sort_number
            }
            PillTab(stringResource(label), selected = order == current, key = scope.key) { onSelect(order) }
        }
    }
}

/** Search command bar for the top bar. Keeps its own text so typing never waits on the debounced results. */
@Composable
private fun SearchInput(
    initial: String,
    autoFocus: Boolean,
    focusRequests: Int,
    scope: Scope,
    onChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val layers = LagarTheme.layers
    var text by remember(initial) { mutableStateOf(initial) }
    val focus = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current
    val hint = stringResource(Res.string.home_search_hint)
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()
    LaunchedEffect(Unit) { if (autoFocus) focus.requestFocus() }
    // Only requests made while this field is shown move focus; the count can be older than the screen.
    val shownAt = remember { focusRequests }
    LaunchedEffect(focusRequests) { if (focusRequests != shownAt) focus.requestFocus() }
    InputFrame(focused = focused, modifier = modifier, idleBorder = layers.accent(scope.key)) {
        Icon(painterResource(Res.drawable.ic_search), null, tint = layers.onTint(scope.key), modifier = Modifier.size(24.dp))
        BasicTextField(
            value = text,
            onValueChange = {
                text = it
                onChange(it)
            },
            modifier = Modifier.weight(1f).focusRequester(focus).semantics { contentDescription = hint },
            singleLine = true,
            textStyle = LagarTheme.type.bodyUi.copy(color = LagarTheme.colors.onSurface),
            cursorBrush = SolidColor(layers.onTint(scope.key)),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { focusManager.clearFocus() }),
            interactionSource = interactionSource,
            decorationBox = { field ->
                Box(contentAlignment = Alignment.CenterStart) {
                    if (text.isEmpty()) {
                        Text(
                            hint,
                            style = LagarTheme.type.bodyUi,
                            color = LagarTheme.colors.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    field()
                }
            },
        )
        searchShortcutHint()?.let { ShortcutHint(it) }
    }
}
