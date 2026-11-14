package app.lagar.ui.tjanster

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.glass
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.domain.Scope
import app.lagar.resources.Res
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.ic_search
import app.lagar.resources.services_audience_all
import app.lagar.resources.services_audience_business
import app.lagar.resources.services_audience_private
import app.lagar.resources.services_empty_text
import app.lagar.resources.services_empty_title
import app.lagar.resources.services_no_match_text
import app.lagar.resources.services_no_match_title
import app.lagar.resources.services_place_kommun_any
import app.lagar.resources.services_place_national
import app.lagar.resources.services_place_region_any
import app.lagar.resources.services_search
import app.lagar.resources.services_topic_business
import app.lagar.resources.services_topic_education
import app.lagar.resources.services_topic_environment
import app.lagar.resources.services_topic_family
import app.lagar.resources.services_topic_health
import app.lagar.resources.services_topic_housing
import app.lagar.resources.services_topic_legal
import app.lagar.resources.services_topic_migration
import app.lagar.resources.services_topic_social_support
import app.lagar.resources.services_topic_tax
import app.lagar.resources.services_topic_vehicles
import app.lagar.resources.services_topic_work
import app.lagar.ui.common.EmptyState
import app.lagar.ui.common.LagarTextField
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.LoadStateHost
import app.lagar.ui.common.PillTab
import app.lagar.ui.common.iconRes
import app.lagar.ui.shell.ShellDimens
import app.lagar.ui.shell.maxContentWidth
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.viewmodel.koinViewModel

/** Tjänster tab: the public service catalogue. [onOpenService] opens a service by its id (`service-<slug>`). */
@Composable
fun TjansterRoute(onOpenService: (String) -> Unit, viewModel: TjansterViewModel = koinViewModel()) {
    val state by viewModel.state.collectAsState()
    TjansterScreen(state = state, onOpenService = onOpenService)
}

/**
 * The services of [state] with a search field, topic chips and an audience switch: a spinner while loading, the
 * error state with retry on failure, an empty state when the API has no services and another when the filters
 * match nothing. The filters live in the screen and survive configuration changes.
 */
@Composable
fun TjansterScreen(state: LoadState<List<ServiceEntry>>, onOpenService: (String) -> Unit) {
    LoadStateHost(state) { entries, shell ->
        if (entries.isEmpty()) {
            Box(Modifier.fillMaxSize().padding(shell), contentAlignment = Alignment.Center) {
                EmptyState(
                    icon = DisplayLayer.Service.iconRes(),
                    title = stringResource(Res.string.services_empty_title),
                    text = stringResource(Res.string.services_empty_text),
                )
            }
        } else {
            ServiceCatalogList(entries, shell, onOpenService)
        }
    }
}

@Composable
private fun ServiceCatalogList(entries: List<ServiceEntry>, shell: PaddingValues, onOpenService: (String) -> Unit) {
    val spacing = LagarTheme.spacing
    var query by rememberSaveable { mutableStateOf("") }
    var topic by rememberSaveable { mutableStateOf<ServiceTopic?>(null) }
    var audience by rememberSaveable { mutableStateOf(ServiceAudience.All) }
    val visible = remember(entries, query, topic, audience) {
        filterServices(entries, ServiceFilter(query, topic, audience))
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize().maxContentWidth(),
        contentPadding = PaddingValues(
            start = spacing.marginMobile,
            end = spacing.marginMobile,
            top = shell.calculateTopPadding() + spacing.md,
            bottom = shell.calculateBottomPadding() + spacing.md,
        ),
        verticalArrangement = Arrangement.spacedBy(spacing.sm),
    ) {
        item(key = "search") {
            LagarTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = stringResource(Res.string.services_search),
                leadingIcon = Res.drawable.ic_search,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            )
        }
        item(key = "audience") {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                ServiceAudience.entries.forEach { a ->
                    PillTab(stringResource(a.labelRes()), selected = a == audience, key = LayerKey.Service) { audience = a }
                }
            }
        }
        item(key = "topics") {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(spacing.xs)) {
                ServiceTopic.entries.forEach { t ->
                    TopicChip(stringResource(t.labelRes()), selected = t == topic) { topic = if (topic == t) null else t }
                }
            }
        }
        if (visible.isEmpty()) {
            item(key = "no-match") {
                EmptyState(
                    icon = Res.drawable.ic_search,
                    title = stringResource(Res.string.services_no_match_title),
                    text = stringResource(Res.string.services_no_match_text),
                    modifier = Modifier.fillMaxWidth().padding(vertical = spacing.lg),
                )
            }
        }
        items(visible, key = { it.service.id }) { entry ->
            ServiceCard(entry, onClick = { onOpenService(entry.service.id) })
        }
    }
}

/**
 * One service: a 3dp indicator in the `service` layer colour, the title as the body publishes it (two lines at
 * most), the issuer in the layer's text colour, a badge for where it is offered, coloured like the scope chip, and for
 * a template kommun service the [KommunLink] to the chosen kommun's website.
 */
@Composable
fun ServiceCard(entry: ServiceEntry, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val layers = LagarTheme.layers
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().glass(GlassTier.Card, shape = MaterialTheme.shapes.medium),
        shape = MaterialTheme.shapes.medium,
        color = Color.Transparent,
    ) {
        Row(Modifier.height(IntrinsicSize.Min)) {
            Box(Modifier.width(3.dp).fillMaxHeight().background(layers.accent(LayerKey.Service)))
            Column(
                modifier = Modifier.weight(1f).padding(horizontal = LagarTheme.spacing.md, vertical = LagarTheme.spacing.sm),
                verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.xs),
            ) {
                Text(
                    entry.service.title,
                    style = LagarTheme.type.bodyUi,
                    color = LagarTheme.colors.onSurface,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(entry.service.issuer, style = LagarTheme.type.labelSm, color = layers.onTint(LayerKey.Service))
                PlaceBadge(entry.place)
                KommunLink(entry.place)
            }
            Icon(
                painterResource(Res.drawable.ic_chevron_right),
                contentDescription = null,
                tint = LagarTheme.colors.onSurfaceVariant,
                modifier = Modifier.align(Alignment.CenterVertically).padding(end = LagarTheme.spacing.sm),
            )
        }
    }
}

@Composable
private fun PlaceBadge(place: ServicePlace) {
    when (place) {
        ServicePlace.National -> LayerBadge(Scope.Nationell.key, stringResource(Res.string.services_place_national))
        is ServicePlace.Region -> LayerBadge(Scope.Region.key, place.name ?: stringResource(Res.string.services_place_region_any))
        is ServicePlace.Kommun -> LayerBadge(Scope.Kommun.key, place.name ?: stringResource(Res.string.services_place_kommun_any))
    }
}

/** A topic filter: tinted in the `service` colour with its text colour when [selected]; tapping toggles it. */
@Composable
private fun TopicChip(text: String, selected: Boolean, onToggle: () -> Unit) {
    val layers = LagarTheme.layers
    Box(
        modifier = Modifier
            .heightIn(min = ShellDimens.TouchTarget)
            .clip(CircleShape)
            .toggleable(value = selected, role = Role.Checkbox, onValueChange = { onToggle() }),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            shape = CircleShape,
            color = if (selected) layers.tint(LayerKey.Service) else LagarTheme.colors.surfaceContainerLowest,
            border = BorderStroke(1.dp, if (selected) layers.border(LayerKey.Service) else LagarTheme.colors.outlineVariant),
        ) {
            Text(
                text,
                style = LagarTheme.type.labelMd,
                color = if (selected) layers.onTint(LayerKey.Service) else LagarTheme.colors.onSurface,
                modifier = Modifier.heightIn(min = 32.dp).padding(horizontal = LagarTheme.spacing.md, vertical = 6.dp),
            )
        }
    }
}

private fun ServiceAudience.labelRes(): StringResource = when (this) {
    ServiceAudience.All -> Res.string.services_audience_all
    ServiceAudience.Private -> Res.string.services_audience_private
    ServiceAudience.Business -> Res.string.services_audience_business
}

private fun ServiceTopic.labelRes(): StringResource = when (this) {
    ServiceTopic.Family -> Res.string.services_topic_family
    ServiceTopic.Work -> Res.string.services_topic_work
    ServiceTopic.Business -> Res.string.services_topic_business
    ServiceTopic.Housing -> Res.string.services_topic_housing
    ServiceTopic.Health -> Res.string.services_topic_health
    ServiceTopic.Tax -> Res.string.services_topic_tax
    ServiceTopic.Vehicles -> Res.string.services_topic_vehicles
    ServiceTopic.Education -> Res.string.services_topic_education
    ServiceTopic.Migration -> Res.string.services_topic_migration
    ServiceTopic.SocialSupport -> Res.string.services_topic_social_support
    ServiceTopic.Environment -> Res.string.services_topic_environment
    ServiceTopic.Legal -> Res.string.services_topic_legal
}
