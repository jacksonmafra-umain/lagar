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
import androidx.compose.runtime.collectAsState
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
import androidx.lifecycle.Lifecycle
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavHostController
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.toRoute
import app.lagar.designsystem.LagarTheme
import app.lagar.resources.Res
import app.lagar.domain.DisplayLayer
import app.lagar.ui.hierarki.HierarkiRoute
import app.lagar.ui.home.HomeRoute
import app.lagar.ui.home.ScopeSheet
import app.lagar.settings.UserPreferences
import app.lagar.ui.navigation.Hierarki
import app.lagar.ui.navigation.LayerList
import app.lagar.ui.navigation.OnboardingLocality
import app.lagar.ui.navigation.OnboardingScope
import app.lagar.ui.navigation.OnboardingWelcome
import app.lagar.ui.navigation.Reader
import app.lagar.ui.navigation.Settings
import app.lagar.ui.navigation.Sparade
import app.lagar.ui.navigation.Splash
import app.lagar.ui.navigation.Tjanster
import app.lagar.ui.navigation.Utforska
import app.lagar.ui.list.LayerListRoute
import app.lagar.ui.onboarding.LocalityStepRoute
import app.lagar.ui.onboarding.OnboardingViewModel
import app.lagar.ui.onboarding.ScopeStepRoute
import app.lagar.ui.onboarding.SplashRoute
import app.lagar.ui.onboarding.WelcomeRoute
import app.lagar.ui.reader.ReaderRoute
import app.lagar.ui.settings.SettingsRoute
import app.lagar.ui.sparade.SparadeScreen
import app.lagar.ui.tjanster.TjansterScreen
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.hazeSource
import kotlinx.coroutines.launch
import org.koin.compose.koinInject
import org.koin.compose.viewmodel.koinViewModel

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
    val preferences = koinInject<UserPreferences>()
    val activeScope by preferences.scope.collectAsState()
    var showScopeSheet by remember { mutableStateOf(false) }
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val backStackEntry by navController.currentBackStackEntryAsState()
    val destination = backStackEntry?.destination
    val selectedTab = Tab.entries.firstOrNull { destination?.hasRoute(it.route::class) == true }

    val density = LocalDensity.current
    var topBarPx by remember { mutableStateOf(0) }
    var bottomBarPx by remember { mutableStateOf(0) }
    val padding = with(density) { PaddingValues(top = topBarPx.toDp(), bottom = bottomBarPx.toDp()) }

    // A second tap during the transition would push a duplicate entry; only navigate from a settled screen.
    fun navigateWhenResumed(route: Any) {
        if (navController.currentBackStackEntry?.lifecycle?.currentState == Lifecycle.State.RESUMED) {
            navController.navigate(route)
        }
    }

    // The steps share one OnboardingViewModel, kept by the Welcome entry, which stays on the stack until onboarding ends.
    @Composable
    fun onboardingEntry(entry: NavBackStackEntry) = remember(entry) { navController.getBackStackEntry<OnboardingWelcome>() }

    // Onboarding is removed from the stack so that back from Home does not return to it.
    fun leaveOnboarding() {
        if (navController.currentBackStackEntry?.lifecycle?.currentState == Lifecycle.State.RESUMED) {
            navController.navigate(Utforska) { popUpTo(OnboardingWelcome) { inclusive = true } }
        }
    }

    fun openLayer(layer: DisplayLayer) = navigateWhenResumed(LayerList(layer.apiLayer, layer.apiType))

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
                    startDestination = Splash,
                    modifier = Modifier.fillMaxSize().hazeSource(hazeState),
                ) {
                    composable<Splash> {
                        SplashRoute(onLoaded = {
                            val next: Any = if (preferences.onboardingDone.value) Utforska else OnboardingWelcome
                            navController.navigate(next) { popUpTo(Splash) { inclusive = true } }
                        })
                    }
                    composable<OnboardingWelcome> { entry ->
                        val onboarding = koinViewModel<OnboardingViewModel>(viewModelStoreOwner = entry)
                        WelcomeRoute(
                            viewModel = onboarding,
                            onContinue = { navigateWhenResumed(OnboardingScope) },
                            onSkip = { onboarding.skip(); leaveOnboarding() },
                        )
                    }
                    composable<OnboardingScope> { entry ->
                        val onboarding = koinViewModel<OnboardingViewModel>(viewModelStoreOwner = onboardingEntry(entry))
                        ScopeStepRoute(
                            viewModel = onboarding,
                            onContinue = { navigateWhenResumed(OnboardingLocality) },
                        )
                    }
                    composable<OnboardingLocality> { entry ->
                        LocalityStepRoute(
                            viewModel = koinViewModel<OnboardingViewModel>(viewModelStoreOwner = onboardingEntry(entry)),
                            onDone = ::leaveOnboarding,
                        )
                    }
                    composable<Utforska> {
                        HomeRoute(
                            onOpenLayer = ::openLayer,
                            onOpenDocument = { navigateWhenResumed(Reader(it)) },
                            // Search is wired by the search task.
                            onOpenSearch = {},
                            onOpenAdvancedSearch = {},
                            onChooseLocation = { showScopeSheet = true },
                        )
                    }
                    composable<Hierarki> { HierarkiRoute(onOpenLayer = ::openLayer) }
                    composable<Sparade> { SparadeScreen() }
                    composable<Tjanster> { TjansterScreen() }
                    composable<LayerList> { entry ->
                        val route = entry.toRoute<LayerList>()
                        LayerListRoute(
                            layer = route.layer,
                            type = route.type,
                            onBack = { navController.popBackStack() },
                            onOpenDocument = { navigateWhenResumed(Reader(it)) },
                        )
                    }
                    composable<Reader> { entry ->
                        ReaderRoute(id = entry.toRoute<Reader>().id, onBack = { navController.popBackStack() })
                    }
                    composable<Settings> { SettingsRoute(onBack = { navController.popBackStack() }) }
                }
            }
            if (selectedTab != null) {
                LagarTopBar(
                    hazeState = hazeState,
                    onMenuClick = { scope.launch { drawerState.open() } },
                    onToggleTheme = onToggleTheme,
                    scope = activeScope,
                    onOpenScopeSheet = { showScopeSheet = true },
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
            if (showScopeSheet) ScopeSheet(onDismiss = { showScopeSheet = false })
        }
    }
}
