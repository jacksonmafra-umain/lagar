package app.lagar.ui.tjanster

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import app.lagar.resources.Res
import app.lagar.resources.ic_layer_apartment
import app.lagar.resources.services_empty_text
import app.lagar.resources.tab_services
import app.lagar.ui.common.EmptyState
import app.lagar.ui.shell.LocalShellPadding
import org.jetbrains.compose.resources.stringResource

@Composable
fun TjansterScreen() {
    Box(Modifier.fillMaxSize().padding(LocalShellPadding.current), contentAlignment = Alignment.Center) {
        EmptyState(
            icon = Res.drawable.ic_layer_apartment,
            title = stringResource(Res.string.tab_services),
            text = stringResource(Res.string.services_empty_text),
        )
    }
}
