package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.data.ListingItem
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.resources.Res
import app.lagar.resources.bookmark_add
import app.lagar.resources.bookmark_remove
import app.lagar.resources.date_days_ago
import app.lagar.resources.date_months_ago
import app.lagar.resources.date_today
import app.lagar.resources.date_yesterday
import app.lagar.resources.date_years_ago
import app.lagar.resources.feed_read_full_text
import app.lagar.resources.ic_bookmark
import app.lagar.resources.ic_bookmark_filled
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.status_in_force
import app.lagar.resources.type_act
import app.lagar.resources.type_fundamental_law
import app.lagar.resources.type_number
import app.lagar.resources.type_ordinance
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.RepealedBadge
import app.lagar.domain.DisplayLayer
import kotlin.time.Clock
import kotlinx.datetime.LocalDate
import kotlinx.datetime.TimeZone
import kotlinx.datetime.todayIn
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

/**
 * One document in the feed: type and number badge in the layer color, how long ago it was issued, up to
 * three lines of title, its status, a bookmark toggle and the "read full text" link. The whole card opens the document.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun FeedCard(
    item: ListingItem,
    bookmarked: Boolean,
    onOpen: () -> Unit,
    onToggleBookmark: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val colors = LagarTheme.colors
    val spacing = LagarTheme.spacing
    val layer = item.displayLayer()
    Surface(
        onClick = onOpen,
        modifier = modifier.fillMaxWidth(),
        shape = MaterialTheme.shapes.large,
        color = colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, colors.outlineVariant),
    ) {
        Column(Modifier.padding(start = spacing.md, top = spacing.md, end = spacing.xs, bottom = spacing.sm)) {
            Row(verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                        verticalArrangement = Arrangement.spacedBy(spacing.xs),
                        itemVerticalAlignment = Alignment.CenterVertically,
                    ) {
                        val label = layer?.let { stringResource(Res.string.type_number, stringResource(it.typeRes()), item.number) } ?: item.number
                        LayerBadge(layer?.key ?: LayerKey.SfsAct, label)
                        item.issued?.let { RelativeDate(it) }
                    }
                    Text(
                        text = item.title,
                        style = LagarTheme.type.bodyUi,
                        color = colors.onSurface,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                BookmarkButton(item.title, bookmarked, onToggleBookmark)
            }
            HorizontalDivider(Modifier.padding(top = spacing.sm, end = spacing.sm), color = colors.outlineVariant)
            FlowRow(
                modifier = Modifier.fillMaxWidth().padding(top = spacing.sm, end = spacing.sm),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalArrangement = Arrangement.spacedBy(spacing.xs),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                if (item.repealed == null) InForce() else RepealedBadge()
                ReadLink(layer?.key ?: LayerKey.SfsAct)
            }
        }
    }
}

@Composable
private fun RelativeDate(issued: String) {
    val age = remember(issued) {
        val date = runCatching { LocalDate.parse(issued) }.getOrNull() ?: return@remember null
        ageOf(date, Clock.System.todayIn(TimeZone.currentSystemDefault()))
    } ?: return
    val text = when (age) {
        Age.Today -> stringResource(Res.string.date_today)
        Age.Yesterday -> stringResource(Res.string.date_yesterday)
        is Age.Days -> pluralStringResource(Res.plurals.date_days_ago, age.n, age.n)
        is Age.Months -> pluralStringResource(Res.plurals.date_months_ago, age.n, age.n)
        is Age.Years -> pluralStringResource(Res.plurals.date_years_ago, age.n, age.n)
    }
    Text(text, style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
}

@Composable
private fun InForce() {
    val layers = LagarTheme.layers
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(layers.accent(LayerKey.Region)))
        Text(stringResource(Res.string.status_in_force), style = LagarTheme.type.labelMd, color = layers.onTint(LayerKey.Region))
    }
}

@Composable
private fun ReadLink(key: LayerKey) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(stringResource(Res.string.feed_read_full_text), style = LagarTheme.type.labelMd, color = LagarTheme.layers.onTint(key))
        Icon(
            painterResource(Res.drawable.ic_chevron_right),
            contentDescription = null,
            tint = LagarTheme.layers.onTint(key),
            modifier = Modifier.size(20.dp),
        )
    }
}

@Composable
private fun BookmarkButton(title: String, bookmarked: Boolean, onToggle: () -> Unit) {
    val description = stringResource(if (bookmarked) Res.string.bookmark_remove else Res.string.bookmark_add, title)
    Box(
        modifier = Modifier
            .size(48.dp)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onToggle)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painterResource(if (bookmarked) Res.drawable.ic_bookmark_filled else Res.drawable.ic_bookmark),
            contentDescription = null,
            tint = if (bookmarked) LagarTheme.layers.onTint(LayerKey.SfsAct) else LagarTheme.colors.onSurfaceVariant,
            modifier = Modifier.size(24.dp),
        )
    }
}

private fun DisplayLayer.typeRes(): StringResource = when (this) {
    DisplayLayer.Fundamental -> Res.string.type_fundamental_law
    DisplayLayer.SfsOrdinance -> Res.string.type_ordinance
    else -> Res.string.type_act
}
