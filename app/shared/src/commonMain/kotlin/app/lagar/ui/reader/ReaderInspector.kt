package app.lagar.ui.reader

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DrawerDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.backhandler.BackHandler
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import app.lagar.data.DocumentMeta
import app.lagar.designsystem.GlassTier
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.generated.LayerKey
import app.lagar.designsystem.glass
import app.lagar.resources.Res
import app.lagar.resources.ic_close
import app.lagar.resources.reader_inspector
import app.lagar.resources.reader_inspector_close
import app.lagar.ui.shell.ShellDimens
import dev.chrisbanes.haze.HazeState
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/**
 * The document's metadata beside its text: facts and source, then the amendments behind their toggle. Shown in the
 * desktop inspector pane and in the tablet drawer ([InspectorDrawer]).
 */
@Composable
internal fun DocumentInspector(
    meta: DocumentMeta,
    amendments: List<AmendmentRow>,
    reprints: List<String>,
    amendmentsOpen: Boolean,
    onToggleAmendments: () -> Unit,
    amendmentLinks: Map<String, String>,
    layer: LayerKey,
    onOpenDocument: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm)) {
        DocumentFacts(meta)
        if (amendments.isNotEmpty() || reprints.isNotEmpty()) {
            HorizontalDivider(color = LagarTheme.colors.outlineVariant)
            AmendmentsToggle(amendments.size, amendmentsOpen, onToggleAmendments)
            if (amendmentsOpen) {
                if (reprints.isNotEmpty()) ReprintsItem(reprints, amendmentLinks, layer, onOpenDocument)
                amendments.forEach { row -> AmendmentItem(row, amendmentLinks[row.number], layer, onOpenDocument) }
            }
        }
    }
}

/**
 * The tablet form of the inspector (DESIGN.md, Layout & Spacing): a Liquid Glass drawer that slides in from the end
 * edge over the dimmed text, closed by its close button, a tap on the scrim or back. [hazeState] is the text it
 * blurs.
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
internal fun InspectorDrawer(
    open: Boolean,
    hazeState: HazeState,
    onClose: () -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    BackHandler(enabled = open, onBack = onClose)
    Box(Modifier.fillMaxSize()) {
        AnimatedVisibility(open, enter = fadeIn(), exit = fadeOut()) {
            Box(
                Modifier
                    .fillMaxSize()
                    .background(DrawerDefaults.scrimColor)
                    .clickable(interactionSource = null, indication = null, onClick = onClose),
            )
        }
        AnimatedVisibility(
            visible = open,
            modifier = Modifier.align(Alignment.CenterEnd),
            enter = slideInHorizontally { it },
            exit = slideOutHorizontally { it },
        ) {
            val title = stringResource(Res.string.reader_inspector)
            Column(
                modifier = Modifier
                    .windowInsetsPadding(WindowInsets.safeDrawing)
                    .padding(LagarTheme.spacing.xs)
                    .width(ShellDimens.DrawerWidth)
                    .fillMaxHeight()
                    .glass(GlassTier.Overlay, hazeState)
                    .semantics { paneTitle = title }
                    .verticalScroll(rememberScrollState())
                    .padding(LagarTheme.spacing.md),
                verticalArrangement = Arrangement.spacedBy(LagarTheme.spacing.sm),
            ) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.weight(1f)) { PaneHeading(title) }
                    CloseButton(onClose)
                }
                content()
            }
        }
    }
}

/** Title of a reader side pane or drawer. */
@Composable
internal fun PaneHeading(text: String) {
    Text(
        text = text,
        style = LagarTheme.type.labelMd,
        fontWeight = FontWeight.Bold,
        color = LagarTheme.colors.onSurfaceVariant,
        modifier = Modifier.semantics { heading() },
    )
}

@Composable
private fun CloseButton(onClick: () -> Unit) {
    val description = stringResource(Res.string.reader_inspector_close)
    Box(
        modifier = Modifier
            .size(ShellDimens.TouchTarget)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Icon(painterResource(Res.drawable.ic_close), contentDescription = null, tint = LagarTheme.colors.onSurfaceVariant)
    }
}
