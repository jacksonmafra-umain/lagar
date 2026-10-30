package app.lagar.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.domain.Scope
import app.lagar.i18n.documentCount
import app.lagar.i18n.formatCount
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.resources.coming_soon
import app.lagar.resources.home_advanced_search
import app.lagar.resources.home_choose_location
import app.lagar.resources.ic_layer_shield
import app.lagar.resources.ic_location_on
import app.lagar.resources.ic_tune
import app.lagar.resources.quick_pick_brottsbalken
import app.lagar.resources.quick_pick_miljobalken
import app.lagar.resources.quick_pick_rattegangsbalken
import app.lagar.resources.scope_institutions
import app.lagar.resources.scope_institutions_soon
import app.lagar.resources.wide_data_updated
import app.lagar.resources.wide_footer_disclaimer
import app.lagar.resources.wide_hero_eyebrow
import app.lagar.resources.wide_hero_text
import app.lagar.resources.wide_hero_title
import app.lagar.resources.wide_quick_picks
import app.lagar.settings.Bookmark
import app.lagar.ui.common.ComingSoonSheet
import app.lagar.ui.common.nameRes
import app.lagar.ui.onboarding.iconRes
import app.lagar.ui.onboarding.nameRes
import app.lagar.ui.shell.DISABLED_ALPHA
import app.lagar.ui.shell.ShellDimens
import app.lagar.ui.shell.WideContent
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Statutes offered as quick picks under the search bar: document id and label. */
private val QuickPicks: List<Pair<String, StringResource>> = listOf(
    "sfs-1962-700" to Res.string.quick_pick_brottsbalken,
    "sfs-1998-808" to Res.string.quick_pick_miljobalken,
    "sfs-1942-740" to Res.string.quick_pick_rattegangsbalken,
)

/**
 * Utforska on wide windows: hero with the scope row, search bar with quick picks, the norm hierarchy grid,
 * the recent documents next to a live preview, and the footer. Every section is capped at the content width.
 */
@Composable
internal fun WideHome(
    data: HomeData,
    shell: PaddingValues,
    bookmarks: List<Bookmark>,
    onOpenLayer: (DisplayLayer) -> Unit,
    onOpenDocument: (String) -> Unit,
    onOpenSearch: (String) -> Unit,
    onOpenAdvancedSearch: () -> Unit,
    onChooseLocation: () -> Unit,
    onSelectScope: (Scope) -> Unit,
    onOpenLocality: (layer: DisplayLayer, code: String, name: String) -> Unit,
    onRetry: () -> Unit,
) {
    val spacing = LagarTheme.spacing
    val home = data.localityHome
    var comingSoon by remember { mutableStateOf<DisplayLayer?>(null) }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = shell.calculateBottomPadding() + spacing.xl),
        verticalArrangement = Arrangement.spacedBy(spacing.xl),
    ) {
        item(key = "hero") {
            Box(
                Modifier
                    .fillMaxWidth()
                    .background(Brush.verticalGradient(listOf(LagarTheme.layers.tint(data.scope.key), Color.Transparent)))
                    .padding(top = shell.calculateTopPadding() + spacing.lg),
            ) {
                WideContent(spacing = spacing.lg) {
                    WideHero(data, onChooseLocation, onSelectScope)
                    WideSearch(data.scope, onOpenSearch, onOpenAdvancedSearch, onOpenDocument, onOpenLayer)
                }
            }
        }
        if (data.unavailable.isNotEmpty()) {
            item(key = "partial") { WideContent { PartialLoadNotice(onRetry) } }
        }
        item(key = "hierarchy") {
            WideContent {
                HierarchySection(
                    counts = data.counts,
                    onLayerClick = { layer -> if ((data.counts[layer] ?: 0) > 0) onOpenLayer(layer) else comingSoon = layer },
                )
            }
        }
        if (home != null) {
            item(key = "locality") {
                WideContent { LocalityRules(data, home.name, onOpenDocument) }
            }
        }
        item(key = "documents") {
            WideContent {
                RecentWithPreview(
                    data = data,
                    bookmarks = bookmarks,
                    onOpenDocument = onOpenDocument,
                    onShowMore = {
                        if (home != null) onOpenLocality(home.level, home.code, home.name) else onOpenLayer(DisplayLayer.SfsAct)
                    },
                )
            }
        }
        item(key = "footer") { WideFooter(data.builtAt) }
    }
    comingSoon?.let { ComingSoonSheet(it) { comingSoon = null } }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun WideHero(data: HomeData, onChooseLocation: () -> Unit, onSelectScope: (Scope) -> Unit) {
    val colors = LagarTheme.colors
    val spacing = LagarTheme.spacing
    val total = data.counts.values.sum()
    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(spacing.lg)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
            Eyebrow(stringResource(Res.string.wide_hero_eyebrow))
            Text(stringResource(Res.string.wide_hero_title), style = LagarTheme.type.headlineLg, color = colors.onSurface)
            Text(
                stringResource(Res.string.wide_hero_text, formatCount(total)),
                style = LagarTheme.type.bodyUi,
                color = colors.onSurfaceVariant,
                modifier = Modifier.widthIn(max = 720.dp),
            )
        }
        if (data.scope != Scope.Nationell) LocationPill(data, onChooseLocation)
    }
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(spacing.sm),
        verticalArrangement = Arrangement.spacedBy(spacing.sm),
        itemVerticalAlignment = Alignment.CenterVertically,
    ) {
        Scope.entries.forEach { scope ->
            val count = scope.layers.sumOf { data.counts[it] ?: 0 }
            ScopePill(
                icon = scope.iconRes(),
                name = stringResource(scope.nameRes()),
                badge = if (count > 0) documentCount(count) else stringResource(Res.string.coming_soon),
                selected = scope == data.scope,
                scope = scope,
                onClick = { onSelectScope(scope) },
            )
        }
        ScopePill(
            icon = Res.drawable.ic_layer_shield,
            name = stringResource(Res.string.scope_institutions),
            badge = stringResource(Res.string.coming_soon),
            selected = false,
            scope = null,
            onClick = null,
        )
        data.builtAt?.let { DataUpdated(it, Modifier.padding(start = spacing.sm)) }
    }
}

@Composable
internal fun Eyebrow(text: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
    ) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(LagarTheme.colors.primary))
        Text(text, style = LagarTheme.type.labelSm, fontWeight = FontWeight.Bold, color = LagarTheme.colors.onSurfaceVariant)
    }
}

/** A scope with its document count; [scope] null is the disabled "Institutional" placeholder. */
@Composable
private fun ScopePill(
    icon: DrawableResource,
    name: String,
    badge: String,
    selected: Boolean,
    scope: Scope?,
    onClick: (() -> Unit)?,
) {
    val layers = LagarTheme.layers
    val colors = LagarTheme.colors
    val key = scope?.key
    val content: @Composable () -> Unit = {
        Row(
            modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).padding(horizontal = LagarTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Icon(painterResource(icon), null, tint = key?.let(layers::onTint) ?: colors.onSurfaceVariant, modifier = Modifier.size(ShellDimens.SmallIconSize))
            Text(
                name,
                style = LagarTheme.type.labelMd,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                color = if (selected && key != null) layers.onTint(key) else colors.onSurface,
            )
            Surface(shape = CircleShape, color = key?.let(layers::tint) ?: colors.surfaceContainer) {
                Text(
                    badge,
                    style = LagarTheme.type.labelSm,
                    color = key?.let(layers::onTint) ?: colors.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = LagarTheme.spacing.sm, vertical = 2.dp),
                )
            }
        }
    }
    val border = BorderStroke(1.dp, if (selected && key != null) layers.accent(key) else colors.outlineVariant)
    val color = if (selected && key != null) layers.tint(key) else colors.surfaceContainerLowest
    if (onClick != null) {
        Surface(onClick = onClick, selected = selected, shape = CircleShape, color = color, border = border, content = content)
    } else {
        val soon = stringResource(Res.string.scope_institutions_soon)
        Surface(
            shape = CircleShape,
            color = color,
            border = border,
            modifier = Modifier.alpha(DISABLED_ALPHA).semantics { contentDescription = soon },
            content = content,
        )
    }
}

@Composable
private fun LocationPill(data: HomeData, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    Surface(
        onClick = onClick,
        shape = CircleShape,
        color = LagarTheme.colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, layers.border(data.scope.key)),
    ) {
        Row(
            modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).padding(horizontal = LagarTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
        ) {
            Icon(painterResource(Res.drawable.ic_location_on), null, tint = layers.onTint(data.scope.key), modifier = Modifier.size(ShellDimens.SmallIconSize))
            Text(
                data.localityName ?: stringResource(Res.string.home_choose_location),
                style = LagarTheme.type.labelMd,
                fontWeight = FontWeight.Bold,
                color = LagarTheme.colors.onSurface,
            )
        }
    }
}

@Composable
private fun DataUpdated(date: String, modifier: Modifier = Modifier) {
    val status = LagarTheme.status
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(status.inForce))
        Text(stringResource(Res.string.wide_data_updated, date), style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun WideSearch(
    scope: Scope,
    onSearch: (String) -> Unit,
    onOpenAdvancedSearch: () -> Unit,
    onOpenDocument: (String) -> Unit,
    onOpenLayer: (DisplayLayer) -> Unit,
) {
    val colors = LagarTheme.colors
    val spacing = LagarTheme.spacing
    Surface(
        shape = MaterialTheme.shapes.large,
        color = colors.surfaceContainerLowest,
        border = BorderStroke(1.dp, colors.outlineVariant),
    ) {
        Column(Modifier.padding(spacing.md), verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                SearchField(scope, onSearch, Modifier.weight(1f))
                Surface(
                    onClick = onOpenAdvancedSearch,
                    shape = CircleShape,
                    color = colors.surfaceContainerLow,
                    border = BorderStroke(1.dp, colors.outlineVariant),
                ) {
                    Row(
                        modifier = Modifier.heightIn(min = ShellDimens.TouchTarget).padding(horizontal = spacing.md),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                    ) {
                        Icon(painterResource(Res.drawable.ic_tune), null, tint = colors.onSurfaceVariant, modifier = Modifier.size(ShellDimens.SmallIconSize))
                        Text(stringResource(Res.string.home_advanced_search), style = LagarTheme.type.labelMd, color = colors.onSurface)
                    }
                }
            }
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                verticalArrangement = Arrangement.spacedBy(spacing.xs),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                Text(stringResource(Res.string.wide_quick_picks), style = LagarTheme.type.labelSm, fontWeight = FontWeight.Bold, color = colors.onSurfaceVariant)
                QuickPick(stringResource(DisplayLayer.Fundamental.nameRes())) { onOpenLayer(DisplayLayer.Fundamental) }
                QuickPicks.forEach { (id, label) -> QuickPick(stringResource(label)) { onOpenDocument(id) } }
            }
        }
    }
}

@Composable
private fun QuickPick(label: String, onClick: () -> Unit) {
    Surface(onClick = onClick, shape = CircleShape, color = LagarTheme.colors.surfaceContainer, modifier = Modifier.heightIn(min = 36.dp)) {
        Box(Modifier.padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm), contentAlignment = Alignment.Center) {
            Text(label, style = LagarTheme.type.labelMd, color = LagarTheme.colors.onSurface)
        }
    }
}

@Composable
private fun WideFooter(builtAt: String?) {
    val colors = LagarTheme.colors
    Column(Modifier.fillMaxWidth().background(colors.surfaceContainerLow).padding(vertical = LagarTheme.spacing.xl)) {
        WideContent {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xl)) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
                    Text(stringResource(Res.string.app_name), style = LagarTheme.type.headlineSm, color = colors.primary)
                    Text(
                        stringResource(Res.string.wide_footer_disclaimer),
                        style = LagarTheme.type.bodyUi,
                        color = colors.onSurfaceVariant,
                        modifier = Modifier.widthIn(max = 640.dp),
                    )
                }
                builtAt?.let { DataUpdated(it) }
            }
            HorizontalDivider(color = colors.outlineVariant)
        }
    }
}
