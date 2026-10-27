package app.lagar

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.navigation.compose.rememberNavController
import app.lagar.data.DataSourceConfig
import app.lagar.designsystem.LagarTheme
import app.lagar.di.appModule
import app.lagar.i18n.ProvideAppLocale
import app.lagar.i18n.systemLanguageTag
import app.lagar.settings.ThemeMode
import app.lagar.settings.UserPreferences
import app.lagar.ui.shell.AppShell
import app.lagar.ui.shell.SystemBarAppearance
import dev.chrisbanes.haze.HazeState
import org.koin.compose.KoinApplication
import org.koin.compose.koinInject
import org.koin.dsl.koinConfiguration

@Composable
fun App() {
    KoinApplication(koinConfiguration { modules(appModule(DataSourceConfig())) }) {
        AppContent()
    }
}

@Composable
private fun AppContent() {
    val preferences = koinInject<UserPreferences>()
    val language by preferences.language.collectAsState()
    val theme by preferences.theme.collectAsState()
    val systemTag = remember { systemLanguageTag() }
    val systemDark = isSystemInDarkTheme()
    val dark = when (theme) {
        ThemeMode.System -> systemDark
        ThemeMode.Light -> false
        ThemeMode.Dark -> true
    }
    // ProvideAppLocale discards remembered state below it on a language switch, so the back stack
    // and the blur source live above it.
    val navController = rememberNavController()
    val hazeState = remember { HazeState() }
    ProvideAppLocale(language.resolve(systemTag)) {
        LagarTheme(darkTheme = dark) {
            SystemBarAppearance(dark)
            AppShell(
                navController = navController,
                hazeState = hazeState,
                onToggleTheme = { preferences.setTheme(if (dark) ThemeMode.Light else ThemeMode.Dark) },
            )
        }
    }
}
