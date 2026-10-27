package app.lagar.ui.common

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import app.lagar.domain.LoadState
import app.lagar.ui.shell.LocalShellPadding

/** Spinner while loading, [ErrorState] on failure, [content] (given the shell padding) when loaded. */
@Composable
internal fun <T> LoadStateHost(state: LoadState<T>, content: @Composable (T, PaddingValues) -> Unit) {
    val shell = LocalShellPadding.current
    when (state) {
        LoadState.Loading -> Box(Modifier.fillMaxSize().padding(shell), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        is LoadState.Failed -> Box(Modifier.fillMaxSize().padding(shell), contentAlignment = Alignment.Center) {
            ErrorState(onRetry = state.retry)
        }
        is LoadState.Loaded -> content(state.value, shell)
    }
}
