package app.lagar.ui.tjanster

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.UriHandler
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.lagar.data.ServiceNormRef
import app.lagar.data.ServiceSummary
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.glass
import app.lagar.domain.DisplayLayer
import app.lagar.domain.LoadState
import app.lagar.resources.Res
import app.lagar.resources.bookmark_add
import app.lagar.resources.bookmark_remove
import app.lagar.resources.ic_bookmark
import app.lagar.resources.ic_bookmark_filled
import app.lagar.resources.ic_chevron_right
import app.lagar.resources.ic_info
import app.lagar.resources.ic_link
import app.lagar.resources.service_based_on
import app.lagar.resources.service_channel_form
import app.lagar.resources.service_channel_office
import app.lagar.resources.service_channel_online
import app.lagar.resources.service_channel_phone
import app.lagar.resources.service_channels
import app.lagar.resources.service_disclaimer
import app.lagar.resources.service_fetched_on
import app.lagar.resources.service_norm_repealed_on
import app.lagar.resources.service_open
import app.lagar.settings.BookmarkStore
import app.lagar.settings.toSavedService
import app.lagar.ui.common.BackTopBar
import app.lagar.ui.common.ErrorState
import app.lagar.ui.common.LagarButton
import app.lagar.ui.common.LayerBadge
import app.lagar.ui.common.RepealedBadge
import app.lagar.ui.common.nameRes
import app.lagar.ui.common.rememberBackTopBarHeight
import app.lagar.ui.common.typeNameRes
import app.lagar.ui.shell.ShellDimens
import app.lagar.ui.shell.maxContentWidth
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject
import org.koin.compose.viewmodel.koinViewModel
import org.koin.core.parameter.parametersOf

/**
 * One public service ([id], `service-<slug>`); [onOpenDocument] opens a norm it is based on in the reader. The
 * bookmark in the top bar saves the service to Sparade.
 */
@Composable
fun ServiceDetailRoute(
    id: String,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    viewModel: ServiceDetailViewModel = koinViewModel(key = "service/" + id) { parametersOf(id) },
    store: BookmarkStore = koinInject(),
) {
    val state by viewModel.state.collectAsState()
    val saved by store.services.collectAsState()
    ServiceDetailScreen(
        state = state,
        onBack = onBack,
        onOpenDocument = onOpenDocument,
        saved = saved.any { it.id == id },
        onToggleSaved = { store.toggleService(it.toSavedService()) },
    )
}

/**
 * The service detail: title and lead as the responsible body publishes them (Swedish in every locale), the issuer,
 * the channels, "Gå till tjänsten" (the e-service when there is one, else the official page, in the system browser),
 * the norms it is based on in their layer colours, the fetch date and the note that lagar is not the authority.
 * Once the service has loaded, a bookmark in the top bar shows whether it is [saved] and calls [onToggleSaved].
 */
@Composable
fun ServiceDetailScreen(
    state: LoadState<ServiceDetail>,
    onBack: () -> Unit,
    onOpenDocument: (String) -> Unit,
    saved: Boolean = false,
    onToggleSaved: ((ServiceSummary) -> Unit)? = null,
) {
    val colors = LagarTheme.colors
    val hazeState = remember { HazeState() }
    var headerHeight by rememberBackTopBarHeight()
    val bottomInset = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()

    Box(Modifier.fillMaxSize().background(colors.surface)) {
        when (state) {
            LoadState.Loading -> Box(Modifier.fillMaxSize().padding(top = headerHeight), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            is LoadState.Failed -> Box(Modifier.fillMaxSize().padding(top = headerHeight), contentAlignment = Alignment.Center) {
                ErrorState(onRetry = state.retry)
            }
            is LoadState.Loaded -> ServiceDetailContent(
                detail = state.value,
                onOpenDocument = onOpenDocument,
                modifier = Modifier
                    .fillMaxSize()
                    .hazeSource(hazeState)
                    .verticalScroll(rememberScrollState())
                    .padding(top = headerHeight, bottom = bottomInset),
            )
        }
        BackTopBar(hazeState, onBack, { headerHeight = it }, Modifier.align(Alignment.TopCenter)) {
            LayerBadge(DisplayLayer.Service, stringResource(DisplayLayer.Service.nameRes()))
            val loaded = (state as? LoadState.Loaded)?.value?.service
            if (loaded != null && onToggleSaved != null) {
                Spacer(Modifier.weight(1f))
                SaveAction(loaded, saved, onToggleSaved)
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ServiceDetailContent(detail: ServiceDetail, onOpenDocument: (String) -> Unit, modifier: Modifier = Modifier) {
    val spacing = LagarTheme.spacing
    val colors = LagarTheme.colors
    val layers = LagarTheme.layers
    val service = detail.service
    val uriHandler = LocalUriHandler.current
    Box(modifier, contentAlignment = Alignment.TopCenter) {
        Column(
            modifier = Modifier.maxContentWidth().fillMaxWidth().padding(horizontal = spacing.marginMobile, vertical = spacing.md),
            verticalArrangement = Arrangement.spacedBy(spacing.md),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                Text(
                    service.title,
                    style = LagarTheme.type.headlineMd,
                    color = colors.onSurface,
                    modifier = Modifier.semantics { heading() },
                )
                Text(service.issuer, style = LagarTheme.type.labelMd, color = layers.onTint(LayerKey.Service))
            }
            detail.lead?.let { Text(it, style = LagarTheme.type.bodyUi, color = colors.onSurface) }
            val channels = service.channels.mapNotNull(::channelLabel)
            if (channels.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                    SectionHeading(stringResource(Res.string.service_channels))
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(spacing.sm),
                        verticalArrangement = Arrangement.spacedBy(spacing.sm),
                    ) {
                        channels.forEach { LayerBadge(LayerKey.Service, stringResource(it)) }
                    }
                }
            }
            LagarButton(
                onClick = { openExternal(uriHandler, service.startUrl) },
                modifier = Modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget),
            ) {
                Icon(painterResource(Res.drawable.ic_link), contentDescription = null, modifier = Modifier.size(18.dp))
                Text(stringResource(Res.string.service_open), style = LagarTheme.type.labelMd, modifier = Modifier.padding(start = spacing.sm))
            }
            detail.place?.let { KommunLink(it) }
            if (service.basedOn.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(spacing.sm)) {
                    SectionHeading(stringResource(Res.string.service_based_on))
                    service.basedOn.forEach { norm -> NormRow(norm, onClick = { onOpenDocument(norm.id) }) }
                }
            }
            AuthorityNote(detail.fetchedOn)
        }
    }
}

/** The bookmark of the top bar: filled in the service level's text colour while the service is saved. */
@Composable
private fun SaveAction(service: ServiceSummary, saved: Boolean, onToggle: (ServiceSummary) -> Unit) {
    val description = stringResource(if (saved) Res.string.bookmark_remove else Res.string.bookmark_add, service.title)
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button) { onToggle(service) }
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painterResource(if (saved) Res.drawable.ic_bookmark_filled else Res.drawable.ic_bookmark),
            contentDescription = null,
            tint = if (saved) LagarTheme.layers.onTint(LayerKey.Service) else LagarTheme.colors.onSurfaceVariant,
        )
    }
}

@Composable
private fun SectionHeading(text: String) {
    Text(
        text,
        style = LagarTheme.type.labelMd,
        fontWeight = FontWeight.Bold,
        color = LagarTheme.colors.onSurfaceVariant,
        modifier = Modifier.semantics { heading() },
    )
}

/**
 * A norm the service is based on: its title in the layer's text colour (never the `base` colour) and its type. A
 * repealed norm is drawn in the Repealed colours with the badge and the date, so it is never shown as in force.
 */
@Composable
private fun NormRow(norm: ServiceNormRef, onClick: () -> Unit) {
    val layers = LagarTheme.layers
    val spacing = LagarTheme.spacing
    val repealed = norm.repealed
    val key = if (repealed != null) LayerKey.Repealed else DisplayLayer.forType(norm.type)?.key ?: LayerKey.SfsAct
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().heightIn(min = ShellDimens.TouchTarget),
        shape = MaterialTheme.shapes.medium,
        color = layers.tint(key),
        border = BorderStroke(1.dp, layers.border(key)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = spacing.md, vertical = spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(spacing.sm),
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                Text(norm.title, style = LagarTheme.type.bodyUi, fontWeight = FontWeight.Bold, color = layers.onTint(key))
                if (repealed != null) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
                        RepealedBadge()
                        Text(
                            stringResource(Res.string.service_norm_repealed_on, repealed),
                            style = LagarTheme.type.labelSm,
                            color = LagarTheme.colors.onSurfaceVariant,
                        )
                    }
                } else {
                    Text(stringResource(typeNameRes(norm.type)), style = LagarTheme.type.labelSm, color = LagarTheme.colors.onSurfaceVariant)
                }
            }
            Icon(painterResource(Res.drawable.ic_chevron_right), contentDescription = null, tint = layers.onTint(key), modifier = Modifier.size(20.dp))
        }
    }
}

/** The fetch date and the note that lagar is not the authority and the official page applies. */
@Composable
private fun AuthorityNote(fetchedOn: String?) {
    val spacing = LagarTheme.spacing
    val colors = LagarTheme.colors
    Surface(
        modifier = Modifier.fillMaxWidth().glass(GlassTier.Card, shape = MaterialTheme.shapes.medium),
        shape = MaterialTheme.shapes.medium,
        color = Color.Transparent,
    ) {
        Row(Modifier.padding(spacing.md), horizontalArrangement = Arrangement.spacedBy(spacing.sm)) {
            Icon(painterResource(Res.drawable.ic_info), contentDescription = null, tint = colors.onSurfaceVariant, modifier = Modifier.size(20.dp))
            Column(verticalArrangement = Arrangement.spacedBy(spacing.xs)) {
                Text(stringResource(Res.string.service_disclaimer), style = LagarTheme.type.labelMd, color = colors.onSurface)
                fetchedOn?.let {
                    Text(stringResource(Res.string.service_fetched_on, it), style = LagarTheme.type.labelSm, color = colors.onSurfaceVariant)
                }
            }
        }
    }
}

/** The label of each channel value; an unknown value has none and is not shown. */
private val channelLabels: Map<String, StringResource> = mapOf(
    "online" to Res.string.service_channel_online,
    "form" to Res.string.service_channel_form,
    "phone" to Res.string.service_channel_phone,
    "office" to Res.string.service_channel_office,
)

private fun channelLabel(channel: String): StringResource? = channelLabels[channel]

/** Opens [url] in the system browser; a malformed URL or a missing handler is ignored rather than crashing. */
private fun openExternal(uriHandler: UriHandler, url: String) {
    runCatching { uriHandler.openUri(url) }
}
