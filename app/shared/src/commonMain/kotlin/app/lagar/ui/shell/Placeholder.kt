package app.lagar.ui.shell

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import app.lagar.designsystem.LagarTheme

/** Space taken by the floating top and bottom bars; screens apply it as content padding. */
internal val LocalShellPadding = compositionLocalOf { PaddingValues() }

/** Stand-in for screens built in later tasks. */
@Composable
internal fun Placeholder(title: String) {
    Box(
        modifier = Modifier.fillMaxSize().padding(LocalShellPadding.current),
        contentAlignment = Alignment.Center,
    ) {
        Text(text = title, style = LagarTheme.type.headlineMd, color = LagarTheme.colors.onSurface)
    }
}
