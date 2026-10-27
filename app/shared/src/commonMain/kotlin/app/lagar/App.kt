package app.lagar

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.app_name
import org.jetbrains.compose.resources.stringResource

@Composable
fun App() {
    LagarTheme(darkTheme = isSystemInDarkTheme()) {
        Surface(modifier = Modifier.fillMaxSize(), color = LagarTheme.colors.surface) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = stringResource(Res.string.app_name),
                    style = LagarTheme.type.headlineLg,
                    color = LagarTheme.colors.onSurface,
                )
            }
        }
    }
}
