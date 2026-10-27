package app.lagar

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import app.lagar.designsystem.LagarTheme
import app.lagar.i18n.ProvideAppLocale
import app.lagar.i18n.systemLanguageTag
import app.lagar.resources.Res
import app.lagar.resources.app_name
import app.lagar.settings.ThemeMode
import app.lagar.settings.UserPreferences
import com.russhwolf.settings.Settings
import org.jetbrains.compose.resources.stringResource

@Composable
fun App() {
    // Temporary wiring until the DI container (Task 4) and app shell (Task 5) take over.
    val preferences = remember { UserPreferences(Settings()) }
    val language by preferences.language.collectAsState()
    val theme by preferences.theme.collectAsState()
    val systemTag = remember { systemLanguageTag() }
    val dark = when (theme) {
        ThemeMode.System -> isSystemInDarkTheme()
        ThemeMode.Light -> false
        ThemeMode.Dark -> true
    }
    ProvideAppLocale(language.resolve(systemTag)) {
        LagarTheme(darkTheme = dark) {
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
}
