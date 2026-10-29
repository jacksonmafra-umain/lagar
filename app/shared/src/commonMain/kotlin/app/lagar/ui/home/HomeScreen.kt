package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.data.ListingItem
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.glass
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.home_choose_location
import app.lagar.resources.home_locality_choose_text
import app.lagar.resources.home_locality_empty_text
import app.lagar.resources.home_locality_empty_title
import app.lagar.resources.home_location_label
import app.lagar.resources.home_scope_kommun_title
import app.lagar.resources.home_scope_region_title
import app.lagar.resources.ic_expand_more
import app.lagar.resources.ic_info
import app.lagar.settings.Bookmark
import app.lagar.settings.UserFocus
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.LoadStateHost
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel

/** Utforska tab: the home of the active scope. Search and location callbacks are wired by the shell. */
@Composable
fun HomeRoute(
    onOpenLayer: (DisplayLayer) -> Unit,
    onOpenDocument: (String) -> Unit,
    onOpenSearch: (String) -> Unit,
    onOpenAdvancedSearch: () -> Unit,
    onChooseLocation: () -> Unit,
    onOpenLocality: (layer: DisplayLayer, code: String, name: String) -> Unit,
    viewModel: HomeViewModel = koinViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val bookmarks by viewModel.bookmarks.collectAsState()
    val focus by viewModel.focus.collectAsState()
    HomeScreen(
        state = state,
        bookmarks = bookmarks,
        focus = focus,
        onOpenLayer = onOpenLayer,
        onOpenDocument = onOpenDocument,
        onOpenSearch = onOpenSearch,
        onOpenAdvancedSearch = onOpenAdvancedSearch,
        onChooseLocation = onChooseLocation,
        onOpenLocality = onOpenLocality,
        onToggleBookmark = viewModel::toggleBookmark,
    )
}

@Composable
fun HomeScreen(
    state: LoadState<HomeData>,
    bookmarks: List<Bookmark>,
    focus: UserFocus,
    onOpenLayer: (DisplayLayer) -> Unit,
    onOpenDocument: (String) -> Unit,
    onOpenSearch: (String) -> Unit,
    onOpenAdvancedSearch: () -> Unit,
    onChooseLocation: () -> Unit,
    onOpenLocality: (layer: DisplayLayer, code: String, name: String) -> Unit,
    onToggleBookmark: (ListingItem) -> Unit,
) {
    LoadStateHost(state) { data, shell ->
        val spacing = LagarTheme.spacing
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = shell.calculateBottomPadding() + spacing.lg),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                    HomeHero(data.scope, shell.calculateTopPadding(), onSearch = onOpenSearch, onOpenAdvancedSearch = onOpenAdvancedSearch)
                    if (data.scope == Scope.Nationell) {
                        LayerChips(data.layers, onOpenLayer, Modifier.padding(horizontal = spacing.marginMobile))
                    } else {
                        LocationCard(data.scope, data.localityName, onChooseLocation, Modifier.padding(horizontal = spacing.marginMobile))
                    }
                }
            }
            if (data.scope == Scope.Nationell) {
                item { ImportantLaws(data, focus, onOpenDocument, Modifier.padding(horizontal = spacing.marginMobile)) }
                item {
                    ExploreFeed(
                        data = data,
                        bookmarks = bookmarks,
                        onOpenDocument = onOpenDocument,
                        onToggleBookmark = onToggleBookmark,
                        onShowMore = { onOpenLayer(DisplayLayer.SfsAct) },
                        modifier = Modifier.padding(horizontal = spacing.marginMobile),
                    )
                }
            } else {
                val name = data.localityName
                val code = data.localityCode
                val level = data.layers.firstOrNull()
                when {
                    name == null || code == null -> item {
                        EmptyState(
                            icon = Res.drawable.ic_info,
                            title = stringResource(Res.string.home_choose_location),
                            text = stringResource(Res.string.home_locality_choose_text),
                        )
                    }
                    level == null || data.localityTotal == 0 -> item {
                        EmptyState(
                            icon = Res.drawable.ic_info,
                            title = stringResource(Res.string.home_locality_empty_title),
                            text = stringResource(Res.string.home_locality_empty_text, name),
                        )
                    }
                    else -> {
                        item { LocalityRules(data, name, onOpenDocument, Modifier.padding(horizontal = spacing.marginMobile)) }
                        item {
                            ExploreFeed(
                                data = data,
                                bookmarks = bookmarks,
                                onOpenDocument = onOpenDocument,
                                onToggleBookmark = onToggleBookmark,
                                onShowMore = { onOpenLocality(level, code, name) },
                                modifier = Modifier.padding(horizontal = spacing.marginMobile),
                            )
                        }
                    }
                }
            }
        }
    }
}

/** Region or kommun selector in the style of the reference's state card; shows the name or a prompt to choose. */
@Composable
private fun LocationCard(scope: Scope, name: String?, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth()
            .glass(GlassTier.Card, shape = MaterialTheme.shapes.large, border = BorderStroke(1.dp, layers.border(scope.key))),
        shape = MaterialTheme.shapes.large,
        color = Color.Transparent,
    ) {
        Row(
            modifier = Modifier.heightIn(min = 60.dp).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.md),
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    text = stringResource(Res.string.home_location_label),
                    style = LagarTheme.type.labelSm,
                    color = layers.onTint(scope.key),
                )
                Text(
                    text = when {
                        name == null -> stringResource(Res.string.home_choose_location)
                        scope == Scope.Region -> stringResource(Res.string.home_scope_region_title, name)
                        else -> stringResource(Res.string.home_scope_kommun_title, name)
                    },
                    style = LagarTheme.type.bodyUi,
                    fontWeight = FontWeight.Bold,
                    color = LagarTheme.colors.onSurface,
                )
            }
            Icon(painterResource(Res.drawable.ic_expand_more), null, tint = LagarTheme.colors.onSurfaceVariant, modifier = Modifier.size(24.dp))
        }
    }
}
