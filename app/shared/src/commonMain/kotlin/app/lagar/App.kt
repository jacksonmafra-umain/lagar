package app.lagar

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.navigation.compose.rememberNavController
import app.lagar.data.DataSourceConfig
import app.lagar.designsystem.LagarTheme
import app.lagar.designsystem.systemReduceTransparency
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

/**
 * Web only: [startRoute] is the screen the address asks for and [startStack] the back stack the browser history saved
 * before a reload (route strings); after the splash the stack is rebuilt, or else the screen opens.
 */
@Composable
fun App(dataSource: DataSourceConfig = DataSourceConfig(), startRoute: Any? = null, startStack: List<String> = emptyList()) {
    KoinApplication(koinConfiguration { modules(appModule(dataSource)) }) {
        AppContent(startRoute, startStack)
    }
}

@Composable
private fun AppContent(startRoute: Any?, startStack: List<String>) {
    val preferences = koinInject<UserPreferences>()
    val language by preferences.language.collectAsState()
    val theme by preferences.theme.collectAsState()
    val reduceTransparency by preferences.reduceTransparency.collectAsState()
    val systemReduceTransparency = systemReduceTransparency()
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
        LagarTheme(darkTheme = dark, reduceTransparency = reduceTransparency.resolve(systemReduceTransparency)) {
            SystemBarAppearance(dark)
            AppShell(
                navController = navController,
                hazeState = hazeState,
                onToggleTheme = { preferences.setTheme(if (dark) ThemeMode.Light else ThemeMode.Dark) },
                startRoute = startRoute,
                startStack = startStack,
            )
        }
    }
}
