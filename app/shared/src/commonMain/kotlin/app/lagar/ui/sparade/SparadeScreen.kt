package app.lagar.ui.sparade

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import app.lagar.resources.Res
import app.lagar.resources.ic_bookmarks
import app.lagar.resources.saved_empty_text
import app.lagar.resources.tab_saved
import app.lagar.ui.common.EmptyState
import app.lagar.ui.shell.LocalShellPadding
import org.jetbrains.compose.resources.stringResource

@Composable
fun SparadeScreen() {
    Box(Modifier.fillMaxSize().padding(LocalShellPadding.current), contentAlignment = Alignment.Center) {
        EmptyState(
            icon = Res.drawable.ic_bookmarks,
            title = stringResource(Res.string.tab_saved),
            text = stringResource(Res.string.saved_empty_text),
        )
    }
}
