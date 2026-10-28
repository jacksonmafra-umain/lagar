package app.lagar.ui.sparade

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import app.lagar.data.ListingItem
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.bookmark_remove
import app.lagar.resources.ic_bookmark_filled
import app.lagar.resources.ic_bookmarks
import app.lagar.resources.saved_empty_text
import app.lagar.resources.saved_empty_title
import app.lagar.settings.Bookmark
import app.lagar.settings.BookmarkStore
import app.lagar.ui.common.EmptyState
import app.lagar.ui.list.StatuteRow
import app.lagar.ui.shell.LocalShellPadding
import app.lagar.ui.shell.ShellDimens
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject

/** Sparade tab: the device-local bookmarks, newest first. */
@Composable
fun SparadeRoute(onOpenDocument: (String) -> Unit, store: BookmarkStore = koinInject()) {
    val bookmarks by store.bookmarks.collectAsState()
    SparadeScreen(bookmarks, onOpenDocument, onRemove = store::toggle)
}

@Composable
fun SparadeScreen(bookmarks: List<Bookmark>, onOpenDocument: (String) -> Unit, onRemove: (Bookmark) -> Unit) {
    val shell = LocalShellPadding.current
    val spacing = LagarTheme.spacing
    if (bookmarks.isEmpty()) {
        Box(Modifier.fillMaxSize().padding(shell), contentAlignment = Alignment.Center) {
            EmptyState(
                icon = Res.drawable.ic_bookmarks,
                title = stringResource(Res.string.saved_empty_title),
                text = stringResource(Res.string.saved_empty_text),
            )
        }
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = spacing.marginMobile,
            end = spacing.marginMobile,
            top = shell.calculateTopPadding() + spacing.md,
            bottom = shell.calculateBottomPadding() + spacing.md,
        ),
        verticalArrangement = Arrangement.spacedBy(spacing.sm),
    ) {
        items(bookmarks, key = { it.id }) { b ->
            val item = ListingItem(b.id, b.title, b.number, b.type, issued = null, repealed = null)
            val layer = b.displayLayer
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(spacing.xs)) {
                StatuteRow(
                    item = item,
                    layer = layer,
                    onClick = { onOpenDocument(b.id) },
                    modifier = Modifier.weight(1f),
                )
                val description = stringResource(Res.string.bookmark_remove, b.title)
                Box(
                    modifier = Modifier
                        .size(ShellDimens.TouchTarget)
                        .clip(CircleShape)
                        .clickable(role = Role.Button) { onRemove(b) }
                        .semantics { contentDescription = description },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        painterResource(Res.drawable.ic_bookmark_filled),
                        contentDescription = null,
                        tint = LagarTheme.layers.onTint(layer?.key ?: LayerKey.SfsAct),
                    )
                }
            }
        }
    }
}
