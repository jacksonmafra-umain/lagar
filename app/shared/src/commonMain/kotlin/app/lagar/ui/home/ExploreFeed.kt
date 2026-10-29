package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import app.lagar.data.ListingItem
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.home_explore_more
import app.lagar.resources.home_favourites_empty_text
import app.lagar.resources.home_favourites_empty_title
import app.lagar.resources.home_show_more
import app.lagar.resources.home_tab_favourites
import app.lagar.resources.home_tab_recent
import app.lagar.resources.ic_bookmarks
import app.lagar.settings.Bookmark
import app.lagar.settings.toListingItem
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.LagarSecondaryButton
import app.lagar.ui.common.PillTab
import org.jetbrains.compose.resources.stringResource

private enum class FeedTab { Recent, Favourites }

/** "Explore more": pill tabs for the newest documents and the user's bookmarks, then the matching cards. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun ExploreFeed(
    data: HomeData,
    bookmarks: List<Bookmark>,
    onOpenDocument: (String) -> Unit,
    onToggleBookmark: (ListingItem) -> Unit,
    onShowMore: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val spacing = LagarTheme.spacing
    var tab by rememberSaveable { mutableStateOf(FeedTab.Recent) }
    val bookmarkedIds = bookmarks.mapTo(HashSet()) { it.id }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
        Text(
            stringResource(Res.string.home_explore_more),
            style = LagarTheme.type.headlineSm,
            color = LagarTheme.colors.onSurface,
        )
        FlowRow(horizontalArrangement = Arrangement.spacedBy(spacing.sm), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
            FeedTab.entries.forEach { entry ->
                PillTab(
                    text = stringResource(if (entry == FeedTab.Recent) Res.string.home_tab_recent else Res.string.home_tab_favourites),
                    selected = tab == entry,
                    key = data.scope.key,
                    onClick = { tab = entry },
                )
            }
        }
        when (tab) {
            FeedTab.Recent -> {
                data.recent.forEach { item ->
                    FeedCard(item, item.id in bookmarkedIds, onOpen = { onOpenDocument(item.id) }, onToggleBookmark = { onToggleBookmark(item) })
                }
                if (data.hasMoreRecent) {
                    LagarSecondaryButton(onClick = onShowMore, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(Res.string.home_show_more))
                    }
                }
            }
            FeedTab.Favourites -> if (bookmarks.isEmpty()) {
                EmptyState(
                    icon = Res.drawable.ic_bookmarks,
                    title = stringResource(Res.string.home_favourites_empty_title),
                    text = stringResource(Res.string.home_favourites_empty_text),
                )
            } else {
                bookmarks.forEach { b ->
                    val item = b.toListingItem()
                    FeedCard(item, bookmarked = true, onOpen = { onOpenDocument(b.id) }, onToggleBookmark = { onToggleBookmark(item) })
                }
            }
        }
    }
}
