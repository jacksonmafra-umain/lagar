package app.lagar.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.backhandler.BackHandler
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.navigation.NavHostController
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.toRoute
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.resources.reader_title
import app.lagar.resources.settings_title
import app.lagar.resources.tab_saved
import app.lagar.resources.tab_services
import app.lagar.domain.DisplayLayer
import app.lagar.ui.hierarki.HierarkiRoute
import app.lagar.ui.navigation.Hierarki
import app.lagar.ui.navigation.LayerList
import app.lagar.ui.navigation.Reader
import app.lagar.ui.navigation.Settings
import app.lagar.ui.navigation.Sparade
import app.lagar.ui.navigation.Tjanster
import app.lagar.ui.navigation.Utforska
import app.lagar.ui.list.LayerListRoute
import app.lagar.ui.utforska.UtforskaRoute
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.launch
import org.jetbrains.compose.resources.stringResource

/**
 * Four-tab shell. The [navController] and [hazeState] are owned by the caller, above the locale
 * provider, so a language switch keeps the back stack.
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun AppShell(
    navController: NavHostController,
    hazeState: HazeState,
    onToggleTheme: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val backStackEntry by navController.currentBackStackEntryAsState()
    val destination = backStackEntry?.destination
    val selectedTab = Tab.entries.firstOrNull { destination?.hasRoute(it.route::class) == true }

    val density = LocalDensity.current
    var topBarPx by remember { mutableStateOf(0) }
    var bottomBarPx by remember { mutableStateOf(0) }
    val padding = with(density) { PaddingValues(top = topBarPx.toDp(), bottom = bottomBarPx.toDp()) }

    fun openLayer(layer: DisplayLayer) = navController.navigate(LayerList(layer.apiLayer, layer.apiType))

    BackHandler(enabled = drawerState.isOpen) { scope.launch { drawerState.close() } }

    ModalNavigationDrawer(
        drawerState = drawerState,
        gesturesEnabled = selectedTab != null,
        drawerContent = {
            LagarDrawerContent(
                hazeState = hazeState,
                onSettingsClick = {
                    scope.launch { drawerState.close() }
                    navController.navigate(Settings) { launchSingleTop = true }
                },
            )
        },
    ) {
        Box(Modifier.fillMaxSize().background(LagarTheme.colors.surface)) {
            CompositionLocalProvider(LocalShellPadding provides if (selectedTab != null) padding else PaddingValues()) {
                NavHost(
                    navController = navController,
                    startDestination = Utforska,
                    modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                ) {
                    composable<Utforska> { UtforskaRoute(onOpenLayer = ::openLayer) }
                    composable<Hierarki> { HierarkiRoute(onOpenLayer = ::openLayer) }
                    composable<Sparade> { Placeholder(stringResource(Res.string.tab_saved)) }
                    composable<Tjanster> { Placeholder(stringResource(Res.string.tab_services)) }
                    composable<LayerList> { entry ->
                        val route = entry.toRoute<LayerList>()
                        LayerListRoute(
                            layer = route.layer,
                            type = route.type,
                            onBack = { navController.popBackStack() },
                            onOpenDocument = { navController.navigate(Reader(it)) },
                        )
                    }
                    composable<Reader> { Placeholder(stringResource(Res.string.reader_title)) }
                    composable<Settings> { Placeholder(stringResource(Res.string.settings_title)) }
                }
            }
            if (selectedTab != null) {
                LagarTopBar(
                    hazeState = hazeState,
                    onMenuClick = { scope.launch { drawerState.open() } },
                    onToggleTheme = onToggleTheme,
                    modifier = Modifier.align(Alignment.TopCenter).onSizeChanged { topBarPx = it.height },
                )
                LagarBottomBar(
                    selected = selectedTab,
                    hazeState = hazeState,
                    onSelect = { tab ->
                        navController.navigate(tab.route) {
                            popUpTo(Utforska) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    modifier = Modifier.align(Alignment.BottomCenter).onSizeChanged { bottomBarPx = it.height },
                )
            }
        }
    }
}
