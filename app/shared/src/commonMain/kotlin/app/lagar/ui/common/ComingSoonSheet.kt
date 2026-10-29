package app.lagar.ui.common

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import app.lagar.designsystem.LagarTheme
import app.lagar.domain.DisplayLayer
import app.lagar.resources.Res
import app.lagar.resources.coming_soon_text
import app.lagar.resources.ic_info
import org.jetbrains.compose.resources.stringResource

/** What a tap on a layer with no documents shows; no list is requested. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComingSoonSheet(layer: DisplayLayer, onDismiss: () -> Unit) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        modifier = Modifier.sheetGlass(),
        shape = SheetShape,
        containerColor = Color.Transparent,
        contentColor = LagarTheme.colors.onSurface,
    ) {
        EmptyState(
            icon = Res.drawable.ic_info,
            title = stringResource(layer.nameRes()),
            text = stringResource(Res.string.coming_soon_text),
            modifier = Modifier.navigationBarsPadding(),
        )
        Spacer(Modifier.height(LagarTheme.spacing.md))
    }
}
